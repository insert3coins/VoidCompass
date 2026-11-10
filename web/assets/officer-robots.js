import * as THREE from "../galactic_map/vendor/three.module.min.js";

const TAU = Math.PI * 2;

// These are articulated meshes, not portrait plates. The owning renderer supplies
// the clock, expression and playback envelope; there are no extra animation loops.
function workshop(parent, uniforms, renderer, scene) {
  renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=.95;
  const root = new THREE.Group(), head = new THREE.Group(), body = new THREE.Group();
  parent.add(root); root.add(head, body); head.position.y = .21;
  const pearl = new THREE.MeshPhysicalMaterial({color:0xd5e3ef, metalness:.38, roughness:.26,
    clearcoat:1, clearcoatRoughness:.18, envMapIntensity:.85});
  const steel = new THREE.MeshStandardMaterial({color:0x566a82, metalness:.85, roughness:.27});
  const dark = new THREE.MeshPhysicalMaterial({color:0x071220, metalness:.50, roughness:.24, clearcoat:1});
  const glass = new THREE.MeshPhysicalMaterial({color:0x071627, metalness:.4, roughness:.17,
    clearcoat:1, envMapIntensity:.4});
  const glow = new THREE.MeshBasicMaterial({color:uniforms.uColour.value});
  const soft = new THREE.MeshBasicMaterial({color:uniforms.uOther.value});
  const white = new THREE.MeshBasicMaterial({color:0xe8faff});
  // The shared frame recess is transparent and renders first. Keep depth testing
  // and writing for the solid parts while joining that same transparent queue.
  for (const m of [pearl,steel,dark,glass,glow,soft,white]) { m.transparent=true; m.forceSinglePass=true; }
  function mesh(g,m,p,at=[0,0,0],scale=null) {
    const o=new THREE.Mesh(g,m);o.position.set(...at);if(scale)o.scale.set(...scale);p.add(o);return o;
  }
  function ball(p,m,at,scale,segments=32) { return mesh(new THREE.SphereGeometry(1,segments,24),m,p,at,scale); }
  function plate(p,m,points,depth,at=[0,0,0],bevel=.015) {
    const shape=new THREE.Shape(points.map(([x,y])=>new THREE.Vector2(x,y)));
    return mesh(new THREE.ExtrudeGeometry(shape,{depth,bevelEnabled:bevel>0,bevelSize:bevel,
      bevelThickness:bevel,bevelSegments:3,steps:1,curveSegments:8}),m,p,at);
  }
  function path(p,m,points,r=.009,closed=false) {
    const curve=new THREE.CatmullRomCurve3(points.map(v=>new THREE.Vector3(...v)),closed,"centripetal");
    return mesh(new THREE.TubeGeometry(curve,Math.max(24,points.length*6),r,6,closed),m,p);
  }
  function dome(p,m,outline,z=.25,bulge=.12) {
    if(THREE.ShapeUtils.isClockWise(outline.map(([x,y])=>new THREE.Vector2(x,y))))outline=[...outline].reverse();
    const curve=new THREE.CatmullRomCurve3(outline.map(([x,y])=>new THREE.Vector3(x,y,0)),true,"centripetal",.18);
    const border=curve.getPoints(128).slice(0,-1),points=[0,0,z+bulge],indices=[],count=border.length,layers=20;
    for(let j=1;j<=layers;j++)for(const v of border){const t=j/layers;points.push(v.x*t,v.y*t,z+bulge*(1-t*t));}
    for(let i=0;i<count;i++)indices.push(0,1+i,1+(i+1)%count);
    for(let j=1;j<layers;j++)for(let i=0;i<count;i++){
      const a=1+(j-1)*count+i,b=1+(j-1)*count+(i+1)%count,c=1+j*count+i,d=1+j*count+(i+1)%count;
      indices.push(a,c,b,b,c,d);
    }
    const g=new THREE.BufferGeometry();g.setAttribute("position",new THREE.Float32BufferAttribute(points,3));g.setIndex(indices);g.computeVertexNormals();
    return mesh(g,m,p);
  }
  function ring(p,m,r,w,at=[0,0,0],segments=64) { return mesh(new THREE.TorusGeometry(r,w,8,segments),m,p,at); }
  function bar(p,m,w,h,at) {
    return plate(p,m,[[-w/2,-h/2],[w/2,-h/2],[w/2,h/2],[-w/2,h/2]],.008,at,Math.min(.006,h/3));
  }
  const room=new THREE.Scene();room.background=new THREE.Color(0x394958);
  for (const [c,at,size] of [[0xf3faff,[-3,4,3],[3,5]],[0x8bb2e1,[4,1,2],[2,5]],
    [0xffffff,[0,5,-2],[4,2]],[0xa6a0d8,[-3,-1,-3],[2,3]]]) {
    const panel=mesh(new THREE.PlaneGeometry(...size),new THREE.MeshBasicMaterial({color:c}),room,at);panel.lookAt(0,0,0);
  }
  const pmrem=new THREE.PMREMGenerator(renderer),environment=pmrem.fromScene(room,.06,.1,20);
  scene.environment=environment.texture;pmrem.dispose();room.traverse(o=>{o.geometry?.dispose();o.material?.dispose();});
  root.add(new THREE.HemisphereLight(0xe0efff,0x263452,1.8));
  const key=new THREE.DirectionalLight(0xffffff,2.5);key.position.set(-2,3,5);root.add(key);
  const fill=new THREE.DirectionalLight(0x9ed9ff,1.5);fill.position.set(3,1,2);root.add(fill);
  const rim=new THREE.DirectionalLight(0xbdb6ff,2.6);rim.position.set(0,2,-3);root.add(rim);
  function colour() {
    glow.color.copy(uniforms.uColour.value);soft.color.copy(uniforms.uOther.value);
    pearl.color.set(0xd5e3ef).lerp(uniforms.uColour.value,.06);
    rim.color.copy(uniforms.uOther.value);fill.color.set(0xc0dfff).lerp(uniforms.uColour.value,.28);
  }
  return {root,head,body,pearl,steel,dark,glass,glow,soft,white,mesh,ball,plate,path,ring,bar,dome,colour,
    destroy(){scene.environment=null;environment.dispose();}};
}

// A small optical bloom pass for the new emissive optics/crystal. Preserve the
// scene's alpha exactly, so it never enlarges the shared bezel or paints a box.
export function createOfficerFinish(renderer,strength=.45) {
  const size=new THREE.Vector2();
  const target=new THREE.WebGLRenderTarget(1,1,{type:renderer.extensions.has("EXT_color_buffer_float")?THREE.HalfFloatType:THREE.UnsignedByteType,depthBuffer:true,samples:4});
  const uniforms={uImage:{value:target.texture},uPixel:{value:new THREE.Vector2(1,1)},uStrength:{value:strength}};
  const material=new THREE.ShaderMaterial({uniforms,depthTest:false,depthWrite:false,
    vertexShader:`varying vec2 vUv;void main(){vUv=uv;gl_Position=vec4(position.xy,0.0,1.0);}`,
    fragmentShader:`varying vec2 vUv;uniform sampler2D uImage;uniform vec2 uPixel;uniform float uStrength;
      void main(){vec4 base=texture2D(uImage,vUv);vec3 bloom=vec3(0.0);float weights=0.0;
        for(int x=-2;x<=2;x++)for(int y=-2;y<=2;y++){
          vec2 offset=vec2(float(x),float(y));float w=exp(-dot(offset,offset)*.6);
          vec3 sampleColour=texture2D(uImage,vUv+offset*uPixel*2.0).rgb;
          float bright=max(sampleColour.r,max(sampleColour.g,sampleColour.b));
          bloom+=sampleColour*smoothstep(.35,1.0,bright)*w;weights+=w;
        }
        gl_FragColor=vec4(base.rgb+bloom/weights*uStrength*base.a,base.a);
        #include <tonemapping_fragment>
        #include <colorspace_fragment>
      }`});
  const scene=new THREE.Scene(),camera=new THREE.Camera(),geometry=new THREE.PlaneGeometry(2,2);
  scene.add(new THREE.Mesh(geometry,material));
  return {
    render(source,view) {
      renderer.getDrawingBufferSize(size);
      if(target.width!==size.x||target.height!==size.y){target.setSize(size.x,size.y);uniforms.uPixel.value.set(1/size.x,1/size.y);}
      renderer.setRenderTarget(target);renderer.render(source,view);const calls=renderer.info.render.calls;
      renderer.setRenderTarget(null);renderer.render(scene,camera);return calls+1;
    },
    destroy(){target.dispose();geometry.dispose();material.dispose();},
  };
}

export function addOfficerHalo(parent,uniforms,identity) {
  const root=new THREE.Group();root.position.z=-.38;parent.add(root);
  const command=identity==="aster";
  const material=new THREE.ShaderMaterial({uniforms:{...uniforms,uSweep:uniforms.uSweep||{value:-1},uDim:uniforms.uDim||{value:0}},
    vertexShader:`varying vec2 vPosition;void main(){vPosition=position.xy;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}`,
    fragmentShader:`uniform vec3 uColour,uOther;uniform float uTime,uEnergy,uSweep,uDim;varying vec2 vPosition;
      void main(){float a=atan(vPosition.y,vPosition.x);float t=.5+.5*sin(a*3.0-uTime*.8);
        float sweep=uSweep<0.0?0.0:exp(-pow(mod(a-uSweep*6.2831853+12.56637,6.2831853)/.22,2.0));
        gl_FragColor=vec4(mix(uColour,uOther,t)+sweep*.6,(.50+t*.30+uEnergy*.2+sweep*.5)*(1.0-uDim*.3));
        #include <colorspace_fragment>
      }`,transparent:true,depthWrite:false,forceSinglePass:true});
  const shape=Array.from({length:96},(_,i)=>new THREE.Vector3(Math.cos(i/96*TAU)*.91,Math.sin(i/96*TAU)*.91,0));
  // Each officer has a moving instrument track inside the shared outer bezel.
  const curve=new THREE.CurvePath();
  for(let i=0;i<shape.length;i++)curve.add(new THREE.LineCurve3(shape[i],shape[(i+1)%shape.length]));
  const track=new THREE.Mesh(new THREE.TubeGeometry(curve,command?120:192,.009,6,true),material);
  track.renderOrder=-2;root.add(track);
  const arcs=new THREE.Group();root.add(arcs);
  for(let i=0;i<3;i++){
    const arc=new THREE.Mesh(new THREE.TorusGeometry(.995,.009,6,64,1.35),material);
    arc.rotation.z=i*TAU/3;arc.renderOrder=-2;arcs.add(arc);
  }
  return {update({clock,reduced,animated}) {
    arcs.rotation.z=clock*(command?.09:-.11);
    track.rotation.x=command?0:.23;track.rotation.y=command?0:Math.sin(clock*.22)*.12;
    root.rotation.y=animated&&!reduced?Math.sin(clock*.4)*.045:0;
  }};
}

// Aster: a naval command unit. A wide smoked visor, titanium cheeks, one
// communications mast and a high collar; no toy optics or hexagonal shell.
export function addAsterOfficer(parent,uniforms,renderer,scene) {
  const w=workshop(parent,uniforms,renderer,scene);
  const {root,head,body,pearl,steel,dark,glass,glow,soft,mesh,ball,plate,path,ring,bar,dome}=w;
  root.name="aster-command-android";head.name="aster-command-helm";head.position.y=.25;
  const armour=pearl.clone();armour.color.set(0x344858);armour.roughness=.30;armour.metalness=.72;
  const titanium=steel.clone();titanium.color.set(0x879aa9);titanium.roughness=.31;
  const outline=[[-.25,.48],[-.41,.37],[-.49,.16],[-.47,-.12],[-.32,-.34],[-.16,-.42],
    [.16,-.42],[.32,-.34],[.47,-.12],[.49,.16],[.41,.37],[.25,.48]];
  plate(head,dark,outline,.25,[0,0,-.16],.035);
  dome(head,armour,outline,.10,.19);
  const visorOutline=[[-.40,.18],[-.45,.11],[-.43,-.045],[-.30,-.10],[.30,-.10],[.43,-.045],[.45,.11],[.40,.18]];
  plate(head,titanium,visorOutline,.025,[0,0,.275],.018);
  dome(head,glass,visorOutline.map(([x,y])=>[x*.98,(y-.04)*.90+.04]),.307,.048);
  // A narrow luminous horizon is seen through the glass, with two focus shutters.
  const horizon=bar(head,soft,.69,.006,[0,.055,.363]);
  const eyes=[];
  for(const side of [-1,1]){
    const eye=new THREE.Group(),lens=new THREE.Group();head.add(eye);eye.add(lens);
    eye.position.set(side*.17,.055,.372);
    plate(lens,glow,[[-.105,.012],[.09,.012],[.105,-.012],[-.09,-.012]],.008,[0,0,0],.003);
    bar(lens,soft,.057,.005,[side*.04,.023,.008]);eyes.push({eye,lens,side});
    const cheek=plate(head,titanium,[[-.075,.10],[.06,.08],[.045,-.16],[-.04,-.22]],.035,[side*.33,-.17,.19],.018);
    cheek.scale.x=side;cheek.rotation.y=side*.18;
    for(let i=0;i<3;i++)bar(head,dark,.055,.009,[side*.335,-.14-i*.035,.246]).rotation.z=-side*.18;
    path(head,soft,[[side*.395,.25,.19],[side*.31,.38,.185],[side*.20,.425,.16]],.005);
  }
  // Offset comms pod and mast distinguish the silhouette from both crewmates.
  const pod=new THREE.Group();head.add(pod);pod.position.set(-.49,.035,-.035);pod.rotation.y=-.30;
  ball(pod,dark,[0,0,0],[.095,.20,.13]);
  ring(pod,titanium,.093,.021,[0,0,.105]);ring(pod,glow,.071,.006,[0,0,.126]);
  ball(pod,glass,[0,0,.13],[.057,.057,.014]);
  path(head,titanium,[[-.45,.21,-.10],[-.52,.43,-.15],[-.50,.59,-.15]],.012);
  ball(head,soft,[-.50,.59,-.15],[.018,.022,.018],16);
  const jaw=new THREE.Group();head.add(jaw);
  plate(head,dark,[[-.18,-.19],[.18,-.19],[.15,-.33],[-.15,-.33]],.02,[0,0,.29],.008);
  plate(jaw,titanium,[[-.24,-.21],[-.13,-.26],[.13,-.26],[.24,-.21],[.16,-.35],[0,-.40],[-.16,-.35]],.025,[0,0,.29],.014);
  const mouth=[];
  for(let i=-2;i<=2;i++)mouth.push(bar(head,glow,.031,.009,[i*.039,-.228,.321]));
  mesh(new THREE.CylinderGeometry(.105,.135,.23,32),dark,body,[0,-.27,0]);
  for(const y of [-.20,-.28,-.35])ring(body,titanium,.12,.009,[0,y,0]).rotation.x=Math.PI/2;
  // Shaped collar and shoulder armour over an articulated underframe.
  const collar=mesh(new THREE.CylinderGeometry(.22,.32,.19,48,1,true,0,Math.PI*1.55),armour,body,[0,-.42,-.025]);
  collar.rotation.y=Math.PI*.23;
  ball(body,dark,[0,-.73,-.04],[.40,.28,.23]);
  const breast=[[-.24,.19],[.24,.19],[.27,-.05],[.14,-.24],[-.14,-.24],[-.27,-.05]];
  plate(body,armour,breast,.10,[0,-.73,.11],.022);
  plate(body,glass,breast.map(([x,y])=>[x*.72,y*.85]),.015,[0,-.73,.23],.012);
  const chest=[];
  for(const side of [-1,1]){
    const shoulder=new THREE.Group();body.add(shoulder);shoulder.position.set(side*.40,-.55,-.02);shoulder.rotation.z=side*.28;
    ball(shoulder,dark,[0,-.06,0],[.18,.20,.17]);
    dome(shoulder,armour,[[-.17,.11],[-.09,.19],[.11,.16],[.20,-.02],[.15,-.15],[-.08,-.10]],.19,.065);
    path(shoulder,titanium,[[-.13,.09,.235],[-.06,.15,.235],[.10,.12,.235],[.17,-.01,.21]],.012);
    path(shoulder,glow,[[-.06,.115,.25],[.08,.095,.25],[.13,.025,.235]],.006);
    plate(body,titanium,[[-.035,.13],[.055,.14],[.045,-.14],[-.04,-.10]],.035,[side*.20,-.49,.15],.008).rotation.z=-side*.42;
    mesh(new THREE.CylinderGeometry(.08,.08,.11,20),dark,body,[side*.42,-.78,-.01]).rotation.z=side*.25;
    ring(body,titanium,.055,.008,[side*.42,-.77,.095]);
    chest.push(bar(body,soft,.011,.14,[side*.135,-.70,.257]));
  }
  bar(body,glow,.095,.009,[0,-.57,.262]);
  ring(body,titanium,.078,.012,[0,-.88,.24]);
  let blink=0,mouthOpenValue=0;
  return {root,head,body,
    update({clock,pose,mouthOpen,reduced,focus,animated,expression={},docking=false}) {
      const {joy=0,worry=0,sad=0,curious=0}=expression,tracking=!reduced&&focus!=="off";
      const phase=(clock+.7)%5.6;
      blink=animated&&!reduced&&phase<.20?Math.sin(phase/.20*Math.PI)**.6:0;
      mouthOpenValue=reduced?0:mouthOpen;jaw.position.y=-mouthOpenValue*.048;
      head.rotation.set(tracking?-pose.y*.12+sad*.08:0,tracking?pose.x*.20:0,tracking?curious*.06:0);
      head.position.y=.25+(animated&&!reduced?Math.sin(clock*1.2)*.005:0)-sad*.014;
      for(const {eye,lens,side} of eyes){
        eye.scale.y=(1-blink*.98)*(1-joy*.22+worry*.45-sad*.18+curious*side*.22);
        eye.rotation.z=side*(worry*.10-sad*.07);lens.position.x=tracking?pose.x*.035:0;
      }
      horizon.scale.y=1-blink*.85;
      mouth.forEach((o,i)=>{o.scale.y=1+mouthOpenValue*(2.5+Math.cos(i)*1.1);o.position.y=-.228-mouthOpenValue*.014;});
      chest.forEach(o=>{o.visible=!docking;});
      w.colour();armour.color.set(0x253746).lerp(uniforms.uColour.value,.035);
      titanium.color.set(0x879aa9).lerp(uniforms.uOther.value,.025);
    },
    inspect:()=>({modelReady:true,modelType:"command-android",eyeRigs:2,blink,mouthMorph:mouthOpenValue}),
    destroy:w.destroy};
}

// Axiom: a precision instrument given a body. Ivory ceramic plates separate at
// the seams, paired camera irises and exposed temple processors suggest curiosity.
export function addAxiomSurveyor(parent,uniforms,renderer,scene) {
  const w=workshop(parent,uniforms,renderer,scene);
  const {root,head,body,pearl,steel,dark,glass,glow,soft,white,mesh,ball,plate,path,ring,bar,dome}=w;
  root.name="axiom-precision-android";head.name="axiom-ceramic-head";head.position.y=.28;
  const ceramic=pearl.clone();ceramic.color.set(0xc7c7ce);ceramic.metalness=.12;ceramic.roughness=.31;
  const brass=steel.clone();brass.color.set(0x967748);brass.roughness=.29;
  ball(head,dark,[0,0,-.035],[.43,.51,.30]);
  const shell=ceramic.clone();
  shell.onBeforeCompile=shader=>{
    shader.vertexShader=shader.vertexShader.replace("#include <common>","#include <common>\nvarying vec3 vShell;")
      .replace("#include <begin_vertex>","#include <begin_vertex>\nvShell=position;");
    shader.fragmentShader=shader.fragmentShader.replace("#include <common>","#include <common>\nvarying vec3 vShell;")
      .replace("#include <clipping_planes_fragment>",`#include <clipping_planes_fragment>
        vec2 eye=vec2((abs(vShell.x)-.187)/.133,(vShell.y-.045)/.106);
        bool seam=abs(vShell.x)<.009&&vShell.y>.20;
        bool mouth=abs(vShell.x)<.12&&vShell.y<-.246&&vShell.y>-.294;
        if(vShell.z>.12&&(dot(eye,eye)<1.0||seam||mouth))discard;`);
  };
  shell.customProgramCacheKey=()=>"axiom-ceramic-optics";
  const shellGeometry=new THREE.SphereGeometry(1,64,40);shellGeometry.scale(.431,.50,.325);mesh(shellGeometry,shell,head);
  // The frontal crest is a structural seam, never a logo or a glowing crown.
  path(head,steel,[[0,.215,.29],[0,.34,.238],[0,.43,.16]],.007);
  plate(head,steel,[[-.014,.13],[.014,.13],[.028,-.075],[0,-.108],[-.028,-.075]],.012,[0,0,.322],.005);
  for(const side of [-1,1]){
    const seam=[[side*.275,.34],[side*.365,.18],[side*.385,-.06],[side*.29,-.30]];
    path(head,steel,seam.map(([x,y])=>[x,y,.325*Math.sqrt(Math.max(0,1-(x/.431)**2-(y/.50)**2))+.003]),.003);
  }
  const eyes=[],processors=[];
  for(const side of [-1,1]){
    const eye=new THREE.Group(),lens=new THREE.Group();head.add(eye);eye.add(lens);
    eye.position.set(side*.187,.045,.296);eye.rotation.y=side*.19;
    ring(lens,steel,.110,.015);ring(lens,glow,.096,.007,[0,0,.015]);
    ball(lens,glass,[0,0,.017],[.087,.083,.035]);
    ring(lens,brass,.059,.011,[0,0,.045]);ring(lens,soft,.043,.004,[0,0,.053]);
    ball(lens,dark,[0,0,.055],[.032,.038,.010],24);
    ball(lens,white,[-.020,.028,.059],[.010,.015,.004],16);eyes.push({eye,lens,side});
    path(head,steel,[[side*.08,.174,.272],[side*.19,.194,.257],[side*.30,.16,.223]],.009);
    // Separate cheek plates expose the black mechanical cheek joint.
    plate(head,steel,[[-.025,.06],[.035,.05],[.06,-.11],[0,-.16]],.025,[side*.32,-.17,.16],.010).scale.x=side;
    path(head,glow,[[side*.30,-.13,.235],[side*.27,-.23,.236]],.005);
    const temple=new THREE.Group();head.add(temple);temple.position.set(side*.414,.055,-.03);
    plate(temple,steel,[[-.03,.20],[.025,.19],[.045,-.20],[-.025,-.19]],.10,[0,0,0],.008);
    for(let i=0;i<3;i++){
      const chip=plate(temple,glass,[[-.028,-.037],[.035,-.037],[.035,.037],[-.028,.037]],.045,[side*.032,.12-i*.105,.085],.006);
      const light=bar(temple,glow,.035,.006,[side*.032,.12-i*.105,.14]);processors.push({chip,light,side,i});
    }
    ball(head,steel,[side*.405,-.21,-.015],[.044,.07,.065],20);
  }
  const jaw=new THREE.Group();head.add(jaw);
  plate(jaw,ceramic,[[-.15,-.27],[.15,-.27],[.14,-.35],[.05,-.41],[-.05,-.41],[-.14,-.35]],.02,[0,0,.25],.015);
  const mouth=new THREE.Mesh(new THREE.PlaneGeometry(.24,.12),new THREE.ShaderMaterial({
    uniforms:{...uniforms,uJaw:{value:0},uSmile:{value:0}},
    vertexShader:`varying vec2 vUv;void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}`,
    fragmentShader:`varying vec2 vUv;uniform vec3 uColour,uOther;uniform float uJaw,uSmile;
      void main(){vec2 p=(vUv-.5)*vec2(.24,.12);float x=p.x/.095;if(abs(x)>1.0)discard;
        float bend=uSmile*.016*(x*x-.3),opening=uJaw*.025*sqrt(max(0.0,1.0-x*x));
        float line=min(abs(p.y-bend-opening*.3),abs(p.y-bend+opening));
        float alpha=1.0-smoothstep(.002,.004,line);if(alpha<.01)discard;
        gl_FragColor=vec4(mix(uColour,uOther,.45),alpha);
        #include <colorspace_fragment>
      }`,transparent:true,depthWrite:false,forceSinglePass:true}));
  mouth.position.set(0,-.267,.291);head.add(mouth);
  // Exposed spindle neck and a solid laboratory chassis, with a dark instrument
  // window in the breastplate for the existing survey crystal.
  mesh(new THREE.CylinderGeometry(.075,.10,.22,24),dark,body,[0,-.30,0]);
  for(const y of [-.23,-.29,-.35])ring(body,steel,.10,.014,[0,y,0]).rotation.x=Math.PI/2;
  ring(body,glow,.101,.005,[0,-.26,0]).rotation.x=Math.PI/2;
  mesh(new THREE.CylinderGeometry(.18,.24,.10,32),steel,body,[0,-.42,0]);
  ball(body,dark,[0,-.73,-.025],[.37,.27,.20]);
  const breast=[[-.23,.17],[.23,.17],[.27,-.02],[.13,-.25],[-.13,-.25],[-.27,-.02]];
  plate(body,ceramic,breast,.09,[0,-.71,.04],.025);
  plate(body,steel,[[-.14,.12],[.14,.12],[.18,-.03],[.09,-.19],[-.09,-.19],[-.18,-.03]],.025,[0,-.70,.16],.014);
  plate(body,glass,[[-.12,.105],[.12,.105],[.15,-.03],[.075,-.17],[-.075,-.17],[-.15,-.03]],.018,[0,-.70,.20],.010);
  const scanBars=[];
  for(const side of [-1,1]){
    const shoulder=new THREE.Group();body.add(shoulder);shoulder.position.set(side*.35,-.57,-.015);shoulder.rotation.z=side*.32;
    ball(shoulder,dark,[0,-.02,0],[.16,.20,.15]);
    dome(shoulder,ceramic,[[-.14,.12],[-.06,.18],[.10,.14],[.17,-.04],[.09,-.15],[-.10,-.08]],.08,.08);
    path(shoulder,steel,[[-.10,.09,.14],[-.04,.14,.16],[.09,.10,.14],[.13,-.02,.12]],.009);
    bar(shoulder,glow,.065,.009,[.01,.09,.17]);
    ball(body,steel,[side*.36,-.80,-.01],[.075,.095,.075],20);
    for(let i=0;i<3;i++)scanBars.push(bar(body,glow,.015,.026,[side*.204,-.63-i*.046,.175]));
  }
  const coreMount=new THREE.Group();coreMount.position.set(0,-.73,.29);body.add(coreMount);
  let blink=0,mouthValue=0,scanProgress=0;
  return {root,head,body,coreMount,
    update({clock,pose,mouthOpen,reduced,focus,animated,expression={},scan=null}) {
      const {joy=0,worry=0,sad=0,curious=0}=expression,tracking=!reduced&&focus!=="off";
      const phase=(clock+1.6)%5.1;
      blink=animated&&!reduced&&phase<.24?Math.sin(phase/.24*Math.PI)**.6:0;mouthValue=reduced?0:mouthOpen;
      head.rotation.set(tracking?-pose.y*.10+sad*.08:0,tracking?pose.x*.19:0,tracking?curious*.13:0);
      head.position.y=.28+(animated&&!reduced?Math.sin(clock*1.25)*.006:0)-sad*.015;
      for(const {eye,lens,side} of eyes){
        eye.scale.y=(1-blink*.97)*(1-joy*.16-sad*.10+worry*.10+curious*side*.09);
        eye.rotation.z=side*(worry*.10-sad*.12);lens.position.set(tracking?pose.x*.018:0,tracking?pose.y*.012:0,0);
      }
      mouth.material.uniforms.uJaw.value=mouthValue;mouth.material.uniforms.uSmile.value=joy-sad*1.5-worry*.4;
      jaw.position.y=-mouthValue*.022;
      scanProgress=scan&&Number(scan.total)>0?Math.min(1,Math.max(0,scan.complete?1:Number(scan.found)/Number(scan.total)||0)):0;
      scanBars.forEach((o,i)=>{o.scale.x=i<Math.round(scanProgress*6)?1.8:.6;});
      processors.forEach(({light,i})=>{light.scale.x=animated&&!reduced?.7+.3*Math.sin(clock*1.4-i):1;});
      w.colour();ceramic.color.set(0xc7c7ce).lerp(uniforms.uColour.value,.035);shell.color.copy(ceramic.color);
    },
    inspect:()=>({modelReady:true,modelType:"precision-android",eyeRigs:2,blink,mouthMorph:mouthValue,scanProgress}),
    destroy:w.destroy};
}

// Meridian's instruments and restrained bearing belong to an old navigator.
// Warm brass, a broad collar and narrow optical windows distinguish the body.
export function addMeridianNavigator(parent,uniforms,renderer,scene) {
  const w=workshop(parent,uniforms,renderer,scene);
  const {root,head,body,steel,dark,glass,glow,soft,mesh,ball,plate,path,ring,bar,dome}=w;
  root.name="meridian-navigator";head.name="meridian-brass-head";head.position.y=.22;
  const brass=steel.clone();brass.color.set(0x927145);brass.metalness=.72;brass.roughness=.36;
  const satin=steel.clone();satin.color.set(0x5e4930);satin.roughness=.43;
  const enamel=glass.clone();enamel.color.set(0x101d30);enamel.roughness=.28;enamel.metalness=.32;
  const outline=[[-.22,.45],[-.39,.34],[-.47,.10],[-.45,-.18],[-.33,-.38],[-.16,-.49],
    [.16,-.49],[.33,-.38],[.45,-.18],[.47,.10],[.39,.34],[.22,.45]];
  plate(head,satin,outline,.23,[0,0,-.14],.035);
  dome(head,brass,outline.map(([x,y])=>[x*.98,y*.98]),.14,.17);
  // The smooth crown is plain; fine seams follow the plates rather than logos.
  path(head,satin,[[-.34,.31,.19],[-.20,.40,.17],[.20,.40,.17],[.34,.31,.19]],.008);
  const eyes=[];
  for(const side of [-1,1]){
    const eye=new THREE.Group(),lens=new THREE.Group();head.add(eye);eye.add(lens);
    eye.position.set(side*.19,.035,.316);eye.rotation.y=side*.08;
    plate(eye,satin,[[-.148,.055],[.125,.055],[.149,-.041],[.12,-.068],[-.125,-.068],[-.148,-.04]],.015,[0,0,0],.012);
    plate(eye,glass,[[-.13,.041],[.117,.041],[.13,-.035],[.11,-.051],[-.115,-.051],[-.13,-.03]],.012,[0,0,.021],.007);
    bar(lens,soft,.17,.018,[0,-.005,.040]);
    bar(lens,glow,.11,.005,[0,.015,.042]);
    ball(lens,dark,[0,-.005,.054],[.018,.022,.006],16);
    eyes.push({eye,lens,side});
    path(head,brass,[[side*.055,.144,.30],[side*.19,.157,.30],[side*.34,.114,.257]],.020);
    plate(head,satin,[[-.035,.07],[.035,.06],[.065,-.13],[.015,-.18]],.020,[side*.32,-.19,.18],.009).scale.x=side;
    path(head,steel,[[side*.34,-.13,.22],[side*.28,-.28,.235],[side*.20,-.34,.22]],.006);
    const gimbal=new THREE.Group();head.add(gimbal);gimbal.position.set(side*.465,-.025,-.02);gimbal.rotation.y=side*.30;
    ball(gimbal,enamel,[0,0,0],[.085,.17,.11]);ring(gimbal,brass,.086,.018,[0,0,.095]);
    ring(gimbal,soft,.061,.004,[0,0,.115]);ball(gimbal,glass,[0,0,.12],[.047,.047,.012],24);
  }
  plate(head,brass,[[-.021,.10],[.021,.10],[.04,-.13],[0,-.17],[-.04,-.13]],.02,[0,0,.30],.007);
  const jaw=new THREE.Group();head.add(jaw);
  plate(head,enamel,[[-.17,-.31],[.17,-.31],[.13,-.43],[-.13,-.43]],.015,[0,0,.255],.007);
  plate(jaw,brass,[[-.18,-.38],[.18,-.38],[.12,-.47],[.055,-.50],[-.055,-.50],[-.12,-.47]],.025,[0,0,.265],.012);
  const mouth=new THREE.Mesh(new THREE.PlaneGeometry(.32,.18),new THREE.ShaderMaterial({
    uniforms:{...uniforms,uJaw:{value:0},uSmile:{value:0}},
    vertexShader:`varying vec2 vUv;void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}`,
    fragmentShader:`varying vec2 vUv;uniform vec3 uColour,uOther;uniform float uJaw,uSmile;
      void main(){vec2 p=(vUv-.5)*vec2(.32,.18);float x=abs(p.x)/.12;if(x>1.0)discard;
        float curve=sqrt(max(0.0,1.0-x*x)),opening=uJaw*.047,bend=uSmile*.021*(x*x-.35);
        float upper=.003+curve*opening*.4+bend,lower=-.003-curve*opening+bend;
        float lip=1.0-smoothstep(.002,.005,min(abs(p.y-upper),abs(p.y-lower)));
        float cavity=smoothstep(lower-.002,lower+.002,p.y)*(1.0-smoothstep(upper-.002,upper+.002,p.y));
        gl_FragColor=vec4(mix(vec3(.004,.009,.016),mix(uColour,uOther,.7),lip),max(cavity*.96,lip));
        #include <colorspace_fragment>
      }`,transparent:true,depthWrite:false,forceSinglePass:true}));
  mouth.position.set(0,-.375,.303);head.add(mouth);
  mesh(new THREE.CylinderGeometry(.12,.15,.19,32),dark,body,[0,-.35,0]);
  for(const y of [-.29,-.35,-.41])ring(body,brass,.135,.011,[0,y,0]).rotation.x=Math.PI/2;
  const collar=mesh(new THREE.CylinderGeometry(.24,.32,.16,48,1,true,0,Math.PI*1.6),enamel,body,[0,-.49,0]);collar.rotation.y=Math.PI*.2;
  ball(body,dark,[0,-.76,-.015],[.40,.25,.23]);
  plate(body,enamel,[[-.25,.17],[.25,.17],[.28,-.05],[.13,-.21],[-.13,-.21],[-.28,-.05]],.10,[0,-.76,.09],.026);
  for(const side of [-1,1]){
    const shoulder=new THREE.Group();body.add(shoulder);shoulder.position.set(side*.39,-.65,-.03);shoulder.rotation.z=side*.32;
    ball(shoulder,enamel,[0,-.03,0],[.19,.19,.16]);
    dome(shoulder,brass,[[-.16,.09],[-.07,.18],[.12,.12],[.19,-.06],[.08,-.13],[-.12,-.08]],.17,.04);
    path(shoulder,satin,[[-.12,.06,.20],[-.04,.13,.22],[.10,.08,.22],[.14,-.035,.20]],.012);
    bar(shoulder,soft,.070,.006,[0,.093,.232]);
    plate(body,brass,[[-.035,.13],[.05,.12],[.065,-.13],[-.02,-.12]],.025,[side*.21,-.56,.15],.012).rotation.z=-side*.35;
    path(body,steel,[[side*.14,-.60,.22],[side*.20,-.75,.24],[side*.12,-.91,.20]],.007);
  }
  ring(body,brass,.135,.019,[0,-.76,.225]);ball(body,glass,[0,-.76,.235],[.114,.114,.022]);
  ring(body,soft,.112,.003,[0,-.76,.261]);
  ring(body,steel,.058,.003,[0,-.76,.264]);ball(body,soft,[0,-.76,.276],[.010,.010,.004],16);
  for(let i=0;i<4;i++){
    const a=i*TAU/4,o=bar(body,brass,.025,.005,[Math.cos(a)*.092,-.76+Math.sin(a)*.092,.263]);o.rotation.z=a;
  }
  const dialNeedle=new THREE.Group();dialNeedle.position.set(0,-.76,.27);body.add(dialNeedle);
  plate(dialNeedle,soft,[[0,.084],[-.014,-.018],[0,-.047],[.014,-.018]],.003,[0,0,0],0);
  let blink=0,mouthValue=0,dialBearing=null;
  return {root,head,body,
    update({clock,pose,mouthOpen,reduced,focus,animated,expression={},bearing=null,bearingVisible=false}) {
      const {joy=0,worry=0,sad=0,curious=0}=expression,tracking=!reduced&&focus!=="off";
      const phase=(clock+1.2)%6.1;
      blink=animated&&!reduced&&phase<.24?Math.sin(phase/.24*Math.PI)**.6:0;mouthValue=reduced?0:mouthOpen;
      head.rotation.set(tracking?-pose.y*.075+sad*.06:0,tracking?pose.x*.14:0,tracking?curious*.07:0);
      head.position.y=.22+(animated&&!reduced?Math.sin(clock*.85)*.004:0)-sad*.012;
      for(const {eye,lens,side} of eyes){
        eye.scale.y=(1-blink*.96)*(1-joy*.16+worry*.22-sad*.12+curious*side*.10);
        eye.rotation.z=side*(worry*.09-sad*.07);lens.position.x=tracking?pose.x*.022:0;
      }
      mouth.material.uniforms.uJaw.value=mouthValue;mouth.material.uniforms.uSmile.value=joy-worry*.5-sad*1.4;
      jaw.position.y=-mouthValue*.032;
      dialBearing=bearingVisible?bearing:null;dialNeedle.visible=bearingVisible;dialNeedle.rotation.z=bearing||0;
      w.colour();brass.color.set(0x927145).lerp(uniforms.uColour.value,.14);satin.color.set(0x5e4930).lerp(uniforms.uColour.value,.10);
    },
    inspect:()=>({modelReady:true,modelType:"navigator-android",eyeRigs:2,blink,mouthMorph:mouthValue,dialBearing}),
    destroy:w.destroy};
}
