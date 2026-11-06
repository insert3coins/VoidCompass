import * as THREE from "../galactic_map/vendor/three.module.min.js";

const TAU = Math.PI * 2;

export function addLyraHalo(parent, uniforms) {
  const halo=new THREE.Group();halo.name="lyra-orbital-halo";halo.position.z=-.34;parent.add(halo);
  const metal=new THREE.MeshStandardMaterial({color:0x294555,metalness:.75,roughness:.32,
    transparent:true,forceSinglePass:true});
  function add(geometry,material) {
    const object=new THREE.Mesh(geometry,material);
    // Behind the robot, after the contrast recess: no light passes across her face.
    object.renderOrder=-2;halo.add(object);return object;
  }
  add(new THREE.TorusGeometry(.926,.026,8,128),metal);
  const material=layer=>new THREE.ShaderMaterial({
    uniforms:{uTime:uniforms.uTime,uEnergy:uniforms.uEnergy,uColour:uniforms.uColour,
      uOther:uniforms.uOther,uLayer:{value:layer}},
    vertexShader:`varying vec3 vPosition,vNormal;
      void main(){vPosition=position;vNormal=normal;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}`,
    fragmentShader:`varying vec3 vPosition,vNormal;uniform float uTime,uEnergy,uLayer;uniform vec3 uColour,uOther;
      void main(){
        float a=atan(vPosition.y,vPosition.x)/6.2831853+.5;
        float phase=fract(a-uTime*.055),segment=fract(phase*3.0);
        float head=pow(segment/.83,8.0);
        vec3 colour=mix(uColour,uOther,smoothstep(.35,.83,segment)*.65);
        float light=.72+uEnergy*.28,alpha=1.0;
        if(uLayer<.5){
          if(segment>.83)discard;
          light*=.42+.58*max(0.0,vNormal.z);
          colour=mix(colour,vec3(.85,.98,1.0),head*.5);
        }else if(uLayer<1.5){
          float ticks=fract((a+uTime*.038)*32.0);
          if(ticks>.60)discard;
          float runner=pow(.5+.5*cos((a+uTime*.075)*18.84956),12.0);
          colour=mix(uOther,uColour,runner);alpha=.22+runner*.76;
        }else{
          float band=exp(-pow((length(vPosition.xy)-.926)/.022,2.0));
          float trail=pow(max(0.0,1.0-segment),5.0);
          alpha=band*(.08+trail*.34+uEnergy*.15);
        }
        gl_FragColor=vec4(colour*light,alpha);
        #include <colorspace_fragment>
      }`,
    transparent:true,depthWrite:false,side:THREE.DoubleSide,forceSinglePass:true,
    blending:layer===2?THREE.AdditiveBlending:THREE.NormalBlending,
  });
  const arcs=add(new THREE.TorusGeometry(.926,.015,8,160),material(0));arcs.position.z=.025;
  const track=add(new THREE.RingGeometry(.865,.879,128),material(1));track.position.z=.02;
  const light=add(new THREE.RingGeometry(.88,.98,128),material(2));light.position.z=.045;
  return {update({clock,reduced,animated}) {
    const moving=animated&&!reduced;
    halo.rotation.x=moving?Math.sin(clock*.47)*.07:0;
    halo.rotation.y=moving?Math.sin(clock*.39)*.10:0;
    metal.color.set(0x294555).lerp(uniforms.uColour.value,.18);
  }};
}

// Articulated geometry, including the visor lenses and jaw. No portrait texture.
export function addLyraRobot(field, uniforms, renderer, scene) {
  const robot = new THREE.Group(), head = new THREE.Group(), body = new THREE.Group();
  robot.name = "lyra-robot"; head.name = "lyra-head";
  field.add(robot); robot.add(head, body); head.position.y = .20; head.scale.setScalar(1.16);
  let blink = 0, mouth = 0;
  const eyeRigs = [], fins = [], lights = [];
  const jaw = {value:0};
  const pearl = new THREE.MeshPhysicalMaterial({color:0xd4e6ef, metalness:.30, roughness:.24,
    clearcoat:1, clearcoatRoughness:.18, envMapIntensity:.85});
  const steel = new THREE.MeshStandardMaterial({color:0x59748b, metalness:.85, roughness:.26});
  const dark = new THREE.MeshStandardMaterial({color:0x081321, metalness:.58, roughness:.30});
  const visor = new THREE.MeshPhysicalMaterial({color:0x031422, metalness:.3, roughness:.21,
    clearcoat:1, clearcoatRoughness:.20, envMapIntensity:.18});
  const glow = new THREE.MeshBasicMaterial({color:uniforms.uColour.value});
  const soft = new THREE.MeshBasicMaterial({color:uniforms.uOther.value});
  const pupil = new THREE.MeshPhysicalMaterial({color:0x051828, metalness:.65, roughness:.14, clearcoat:1});
  const glint = new THREE.MeshBasicMaterial({color:0xe7fbff});
  const allMaterials = [pearl, steel, dark, visor, glow, soft, pupil, glint];
  // The shared frame recess is transparent; draw the body after it, with depth intact.
  allMaterials.forEach(material => {material.transparent=true; material.forceSinglePass=true;});

  function mesh(geometry, material, parent, position=[0,0,0], scale=null) {
    const object = new THREE.Mesh(geometry,material); object.position.set(...position);
    if(scale)object.scale.set(...scale); parent.add(object); return object;
  }
  function sphere(parent, material, position, scale, segments=40) {
    return mesh(new THREE.SphereGeometry(1,segments,28),material,parent,position,scale);
  }
  function tube(parent, material, points, radius=.012, closed=false) {
    const curve=new THREE.CatmullRomCurve3(points.map(p=>new THREE.Vector3(...p)),closed,"centripetal");
    return mesh(new THREE.TubeGeometry(curve,Math.max(24,points.length*5),radius,6,closed),material,parent);
  }
  function ring(parent, material, radius, width, position, rotation=null) {
    const object=mesh(new THREE.TorusGeometry(radius,width,8,56),material,parent,position);
    if(rotation)object.rotation.set(...rotation);return object;
  }
  function capsule(parent,material,width,height,depth,position) {
    const r=height/2,shape=new THREE.Shape();
    shape.moveTo(-width/2+r,-r);shape.lineTo(width/2-r,-r);
    shape.absarc(width/2-r,0,r,-Math.PI/2,Math.PI/2,false);
    shape.lineTo(-width/2+r,r);shape.absarc(-width/2+r,0,r,Math.PI/2,Math.PI*1.5,false);
    return mesh(new THREE.ExtrudeGeometry(shape,{depth,bevelEnabled:false,curveSegments:10}),material,parent,position);
  }

  const room=new THREE.Scene();room.background=new THREE.Color(0x394958);
  for(const [colour,p,s] of [[0xf1faff,[-3,4,3],[3,5,1]],[0x6dadd8,[4,1,2],[2,5,1]],
    [0xffffff,[0,5,-2],[4,2,1]],[0x8b9bbe,[-3,-1,-3],[2,3,1]]]) {
    const panel=mesh(new THREE.PlaneGeometry(...s.slice(0,2)),new THREE.MeshBasicMaterial({color:colour}),room,p);
    panel.lookAt(0,0,0);
  }
  const pmrem=new THREE.PMREMGenerator(renderer), environment=pmrem.fromScene(room,.06,.1,20);
  scene.environment=environment.texture;pmrem.dispose();
  room.traverse(o=>{o.geometry?.dispose();o.material?.dispose();});
  const ambient=new THREE.HemisphereLight(0xd9efff,0x293b55,1.8);field.add(ambient);
  const key=new THREE.DirectionalLight(0xffffff,2.4);key.position.set(-2,3,5);field.add(key);
  const fill=new THREE.DirectionalLight(0x96d9ff,1.6);fill.position.set(3,1,2);field.add(fill);
  const rim=new THREE.DirectionalLight(0x93beff,2.8);rim.position.set(0,2,-3);field.add(rim);

  // A recessed visor and mouth cut through the actual curved shell.
  const shellMaterial=pearl.clone();
  shellMaterial.onBeforeCompile=shader=>{
    shader.uniforms.uLyraJaw=jaw;
    shader.vertexShader=shader.vertexShader.replace("#include <common>","#include <common>\nuniform float uLyraJaw;varying vec3 vShell;");
    shader.vertexShader=shader.vertexShader.replace("#include <begin_vertex>",`#include <begin_vertex>
      vShell=position;
      float lower=(1.0-smoothstep(-.415,-.385,position.y))*(1.0-smoothstep(.10,.32,abs(position.x)));
      transformed.y-=uLyraJaw*.045*lower;transformed.z+=uLyraJaw*.012*lower;`);
    shader.fragmentShader=shader.fragmentShader.replace("#include <common>","#include <common>\nuniform float uLyraJaw;varying vec3 vShell;");
    shader.fragmentShader=shader.fragmentShader.replace("#include <clipping_planes_fragment>",`#include <clipping_planes_fragment>
      vec2 q=abs(vec2(vShell.x,vShell.y+.045))-vec2(.422,.103);
      float screen=length(max(q,0.0))+min(max(q.x,q.y),0.0)-.105;
      float smile=-.389+.035*pow(vShell.x/.16,2.0);
      float opening=.006+uLyraJaw*.035*(1.0-pow(vShell.x/.16,2.0));
      if(vShell.z>.17&&(screen<0.0||(abs(vShell.x)<.16&&vShell.y<smile+.006&&vShell.y>smile-opening)))discard;`);
  };
  shellMaterial.customProgramCacheKey=()=>"lyra-shell-jaw";
  const shellGeometry=new THREE.SphereGeometry(1,72,48);shellGeometry.scale(.605,.585,.445);
  mesh(shellGeometry,shellMaterial,head);
  sphere(head,dark,[0,0,-.005],[.587,.57,.425]);

  const outline=[];
  for(let i=0;i<96;i++) {
    const angle=i/96*TAU,cos=Math.cos(angle),sin=Math.sin(angle);
    const x=Math.sign(cos)*(.422+.105*Math.abs(cos)), y=-.045+Math.sign(sin)*(.103+.105*Math.abs(sin));
    const z=.443-.11*(x/.53)**2-.025*((y+.045)/.21)**2;
    outline.push([x,y,z]);
  }
  const screenPositions=[0,-.045,.432],screenIndices=[];
  // Concentric rings make the visor genuinely convex, including its centre.
  for(let layer=1;layer<=10;layer++)for(const [x,y] of outline) {
    const f=layer/10,px=x*f,py=-.045+(y+.045)*f;
    screenPositions.push(px,py,.432-.11*(px/.53)**2-.025*((py+.045)/.21)**2);
  }
  for(let i=0;i<96;i++)screenIndices.push(0,1+i,1+(i+1)%96);
  for(let layer=1;layer<10;layer++)for(let i=0;i<96;i++) {
    const a=1+(layer-1)*96+i,b=1+(layer-1)*96+(i+1)%96,c=1+layer*96+i,d=1+layer*96+(i+1)%96;
    screenIndices.push(a,c,b,b,c,d);
  }
  const screenGeometry=new THREE.BufferGeometry();screenGeometry.setAttribute("position",new THREE.Float32BufferAttribute(screenPositions,3));
  screenGeometry.setIndex(screenIndices);screenGeometry.computeVertexNormals();
  mesh(screenGeometry,visor,head);
  tube(head,steel,outline,.015,true);

  for(const side of [-1,1]) {
    const eye=new THREE.Group();head.add(eye);eye.position.set(side*.255,-.045,.424);eye.scale.setScalar(1.1);
    eye.rotation.y=side*.16;
    const lens=new THREE.Group();eye.add(lens);
    ring(lens,steel,.143,.018,[0,0,0]);
    ring(lens,glow,.123,.014,[0,0,.018]);
    ring(lens,soft,.139,.003,[0,0,.016]);
    sphere(lens,pupil,[0,0,.018],[.105,.105,.035],32);
    ring(lens,steel,.082,.006,[0,0,.048]);
    ring(lens,glow,.075,.003,[0,0,.052]);
    sphere(lens,dark,[0,0,.055],[.048,.052,.012],24);
    sphere(lens,glint,[-.034,.037,.057],[.019,.026,.006],16);
    sphere(lens,glow,[.029,-.029,.058],[.008,.010,.005],12);
    eyeRigs.push({eye,lens,side});
    const ear=new THREE.Group();ear.position.set(side*.616,-.01,-.02);ear.rotation.z=Math.PI/2;head.add(ear);
    mesh(new THREE.CylinderGeometry(.205,.205,.065,40),dark,ear);
    mesh(new THREE.CylinderGeometry(.184,.184,.088,40),steel,ear);
    mesh(new THREE.CylinderGeometry(.161,.161,.096,40),pearl,ear);
    ring(ear,glow,.148,.007,[0,side*.052,0],[Math.PI/2,0,0]);
    const fin=new THREE.Group();fin.position.set(side*.485,.25,-.12);fin.scale.setScalar(.72);fin.rotation.z=-side*.25;head.add(fin);fins.push({fin,side});
    sphere(fin,dark,[0,.13,0],[.098,.25,.10],32);
    sphere(fin,pearl,[side*.018,.14,.018],[.082,.233,.086],32);
    tube(fin,glow,[[side*.025,-.035,.07],[side*.04,.08,.076],[side*.035,.21,.053],[0,.30,.02]],.009);
    tube(head,steel,[[side*.56,-.25,.16],[side*.49,-.36,.23],[side*.41,-.44,.22]],.025);
    capsule(head,soft,.055,.012,.005,[side*.45,-.27,.31]).rotation.z=side*.32;
  }
  capsule(head,glow,.065,.009,.008,[0,-.52,.204]);
  // The articulated neck and shoulder armour remain visible below the face.
  mesh(new THREE.CylinderGeometry(.105,.125,.20,32),dark,body,[0,-.37,0]);
  for(const y of [-.32,-.37,-.42])ring(body,steel,.115,.012,[0,y,0],[Math.PI/2,0,0]);
  mesh(new THREE.CylinderGeometry(.16,.255,.15,40,1,true),steel,body,[0,-.48,-.015]);
  ring(body,glow,.175,.006,[0,-.46,0],[Math.PI/2,0,0]);
  sphere(body,dark,[0,-.76,-.045],[.38,.30,.22]);
  for(const side of [-1,1]) {
    const shoulder=sphere(body,pearl,[side*.36,-.70,-.015],[.19,.21,.19]);shoulder.rotation.z=side*.45;
    tube(body,steel,[[side*.14,-.52,.15],[side*.24,-.62,.20],[side*.28,-.82,.14]],.043);
    tube(body,pearl,[[side*.16,-.52,.178],[side*.24,-.65,.24],[side*.27,-.80,.18]],.028);
    ring(body,glow,.064,.010,[side*.42,-.71,.145]);
    sphere(body,dark,[side*.34,-.91,-.005],[.13,.16,.13]);
  }
  for(let i=0;i<4;i++) lights.push(capsule(body,glow,.19-i*.037,.014,.014,[0,-.63-i*.047,.175+(i===0?0:.018)]));
  ring(body,steel,.105,.02,[0,-.91,.16]);

  return {
    update({clock,pose,mouthOpen,reduced,focus,animated}) {
      const phase=(clock+1.15)%5.3;
      blink=animated&&!reduced&&phase<.22?Math.sin(phase/.22*Math.PI)**.6:0;
      mouth=reduced?0:mouthOpen;jaw.value=mouth;
      const tracking=!reduced&&focus!=="off";
      head.rotation.set(tracking?-pose.y*.065:0,tracking?pose.x*.08:0,
        animated&&tracking?Math.sin(clock*.53)*.025:0);
      head.position.y=.20+(animated&&!reduced?Math.sin(clock*1.4)*.007:0);
      for(const {eye,lens,side} of eyeRigs) {
        eye.scale.y=1.1*(1-blink*.96);
        lens.position.x=tracking?pose.x*.022:0;lens.position.y=tracking?pose.y*.014:0;
        lens.rotation.z=animated?side*Math.sin(clock*.6)*.035:0;
      }
      for(const {fin,side} of fins)fin.rotation.z=-side*.25+(animated&&!reduced?Math.sin(clock*1.1)*side*.035:0);
      glow.color.copy(uniforms.uColour.value);soft.color.copy(uniforms.uOther.value);
      pearl.color.set(0xd4e6ef).lerp(uniforms.uColour.value,.045);
      fill.color.set(0xc0e6ff).lerp(uniforms.uColour.value,.28);
      rim.color.copy(uniforms.uOther.value).lerp(uniforms.uColour.value,.6);
      lights.forEach((light,i)=>{light.scale.x=animated&&!reduced?1+.10*Math.sin(clock*2-i*.65)+mouth*.15:1;});
    },
    inspect:()=>({modelReady:true,modelType:"articulated-robot",blink,mouthMorph:mouth,eyeRigs:eyeRigs.length}),
    destroy(){scene.environment=null;environment.dispose();},
  };
}
