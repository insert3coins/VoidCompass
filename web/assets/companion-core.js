import * as THREE from "../galactic_map/vendor/three.module.min.js";

// Shared reactive geometry; the owning display supplies its clock and audio
// envelope, so the core adds no timers or animation loop of its own.
export function createCompanionCore({identity, time, energy, colour, highlight}) {
  const command = identity === "aster";
  const group = new THREE.Group(), lattice = new THREE.Group();
  group.name = `${identity}-reactive-core`;
  group.add(lattice);
  // uGlow/uDim/uWorry: the mood (5.7.6). uLit: facets lit, one per body scanned; uFlash: all found.
  const uniforms = {uTime:time,uEnergy:energy,uColour:colour,uOther:highlight,
    uMode:{value:0},uLinks:{value:0},uViewport:{value:new THREE.Vector2(144,144)},
    uGlow:{value:0},uDim:{value:0},uWorry:{value:0},uLit:{value:0},uFlash:{value:0}};
  const geometry = command ? new THREE.CylinderGeometry(.205,.205,.19,6,1) : new THREE.IcosahedronGeometry(.32,0);
  if (command) geometry.rotateX(Math.PI/2);
  // The crystal's twenty faces, numbered (its geometry is three vertices a face).
  const faceCount = command ? 0 : geometry.getAttribute("position").count / 3;
  geometry.setAttribute("aFace",new THREE.Float32BufferAttribute(
    Array.from({length:geometry.getAttribute("position").count},(_,i)=>command?999:Math.floor(i/3)),1));
  const facets = new THREE.Mesh(geometry,new THREE.ShaderMaterial({
    uniforms,
    vertexShader:`attribute float aFace;varying vec3 vNormal;varying vec3 vPos;varying float vFace;
      void main(){vNormal=normalize(normalMatrix*normal);vPos=position;vFace=aFace;
        gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}`,
    fragmentShader:`varying vec3 vNormal;varying vec3 vPos;varying float vFace;
      uniform vec3 uColour,uOther;uniform float uTime,uEnergy,uMode,uGlow,uDim,uLit,uFlash;
      void main(){float rim=pow(1.0-abs(vNormal.z),2.0);
        float scan=pow(max(0.0,1.0-abs(vPos.y-sin(uTime*1.7)*.32)/.065),2.0);
        float lit=1.0-step(uLit,vFace+.5);
        vec3 colour=mix(mix(uColour,uOther,.25+rim*.5),uOther,lit*.85);
        float alpha=.025+rim*.055+uEnergy*.055+scan*.07*step(.5,uMode)+lit*(.30+uFlash*.22);
        gl_FragColor=vec4(colour,alpha*(1.0+uGlow*.7)*(1.0-uDim*.45));
        #include <colorspace_fragment>
      }`,
    transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,
    side:THREE.DoubleSide,forceSinglePass:true,
  }));
  lattice.add(facets);

  // Screen-space ribbons keep the lattice readable at 54px as well as 256px.
  function ribbons(segments, links=false) {
    const starts=[],ends=[],sides=[],along=[],indices=[];
    for(let i=0;i<segments.length;i++) {
      const [start,end]=segments[i];
      for(const [t,side] of [[0,-1],[1,-1],[0,1],[0,1],[1,-1],[1,1]]) {
        starts.push(...start);ends.push(...end);along.push(t);sides.push(side);indices.push(i);
      }
    }
    const paths=new THREE.BufferGeometry();
    paths.setAttribute("position",new THREE.Float32BufferAttribute(starts,3));
    paths.setAttribute("aEnd",new THREE.Float32BufferAttribute(ends,3));
    paths.setAttribute("aSide",new THREE.Float32BufferAttribute(sides,1));
    paths.setAttribute("aAlong",new THREE.Float32BufferAttribute(along,1));
    paths.setAttribute("aIndex",new THREE.Float32BufferAttribute(indices,1));
    const material=new THREE.ShaderMaterial({
      uniforms:{...uniforms,uRoute:{value:links?1:0}},
      vertexShader:`attribute vec3 aEnd;attribute float aSide,aAlong,aIndex;
        uniform vec2 uViewport;varying float vSide,vAlong,vIndex;
        void main(){vec4 a=projectionMatrix*modelViewMatrix*vec4(position,1.0);
          vec4 b=projectionMatrix*modelViewMatrix*vec4(aEnd,1.0);
          vec2 d=(b.xy/b.w-a.xy/a.w)*uViewport;
          vec2 normal=vec2(-d.y,d.x)/max(length(d),.001);
          vec4 p=mix(a,b,aAlong);p.xy+=normal*aSide*1.25/uViewport*p.w;
          gl_Position=p;vSide=aSide;vAlong=aAlong;vIndex=aIndex;}`,
      fragmentShader:`uniform vec3 uColour,uOther;uniform float uTime,uEnergy,uMode,uRoute,uLinks,uGlow,uDim,uWorry;
        varying float vSide,vAlong,vIndex;
        void main(){float edge=1.0-smoothstep(.45,1.0,abs(vSide));
          float speed=mix(.22,.70,step(1.5,uMode));
          float phase=fract(uTime*speed+vIndex*.137);
          float packet=pow(max(0.0,1.0-abs(vAlong-phase)*6.0),3.0);
          float alpha=edge*(.48+packet*.46+uEnergy*.18);
          if(uRoute>.5)alpha=edge*packet*uLinks*.8;
          vec3 colour=mix(uColour,uOther,packet*.85);
          float flicker=1.0-uWorry*.35*step(.55,fract(uTime*6.0+vIndex*.31));
          gl_FragColor=vec4(colour,alpha*(1.0+uGlow*.45)*(1.0-uDim*.4)*flicker);
          #include <colorspace_fragment>
        }`,
      transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,side:THREE.DoubleSide,forceSinglePass:true,
    });
    const mesh=new THREE.Mesh(paths,material);mesh.frustumCulled=false;return mesh;
  }
  const edges=new THREE.EdgesGeometry(geometry), positions=edges.getAttribute("position"), segments=[];
  for(let i=0;i<positions.count;i+=2) {
    segments.push([[positions.getX(i),positions.getY(i),positions.getZ(i)],
      [positions.getX(i+1),positions.getY(i+1),positions.getZ(i+1)]]);
  }
  edges.dispose();
  lattice.add(ribbons(segments));
  const routes=[];
  for(let i=0;i<6;i++) {
    const a=(i+.5)/6*Math.PI*2, outer=command?.43:.54, inner=command?.21:.30;
    routes.push([[Math.cos(a)*outer,Math.sin(a)*outer,0],[Math.cos(a)*inner,Math.sin(a)*inner,0]]);
  }
  group.add(ribbons(routes,true));
  let mode="idle",amplitude=0,spin=0,lastClock=null,lit=0;
  const calm={joy:0,worry:0,sad:0,curious:0};
  return {
    group,
    resize(width,height){uniforms.uViewport.value.set(width,height);},
    // scan: {found,total,complete} lights a facet per body found (the crystal only).
    update({state,clock,level=0,animated=true,pulse=0,expression=calm,scan=null}) {
      mode=state;amplitude=level;
      const {joy=0,worry=0,sad=0,curious=0}=expression||calm;
      uniforms.uMode.value={idle:0,listening:1,working:2,speaking:3,alert:4,charging:5}[state]||0;
      uniforms.uLinks.value=["listening","working","charging"].includes(state)?1:Math.min(1,level*.75+pulse);
      uniforms.uGlow.value=joy;uniforms.uDim.value=sad;uniforms.uWorry.value=worry;
      // Wary holds the core still; downcast slows it.
      const step=lastClock===null?0:Math.max(0,clock-lastClock);lastClock=clock;
      spin+=step*Math.max(.05,1-worry*.95-sad*.5);
      lattice.rotation.set((command?.24:.35)+Math.sin(spin*.43)*.14-sad*.18,
        (command?.40:.55)+spin*(command?.13:.20)+curious*.7,spin*(command?-.07:.055));
      const breath=animated?Math.sin(clock*1.2)*.025:0;
      const focus=state==="listening"?-.06:state==="alert"?.035:0;
      lattice.scale.setScalar((1+breath+level*.14+focus+pulse*.04)*(1+joy*.08-sad*.06-worry*.04));
      lit=!faceCount||!scan||!(Number(scan.total)>0)?0
        :scan.complete?faceCount:Math.min(faceCount,Math.round(faceCount*Math.min(1,Number(scan.found)/Number(scan.total))));
      uniforms.uLit.value=lit;uniforms.uFlash.value=scan?.complete?1:0;
    },
    inspect(){return {design:command?"command-prism":"lattice-crystal",state:mode,energy:amplitude,
      scale:lattice.scale.x,rotation:lattice.rotation.toArray().slice(0,3),links:uniforms.uLinks.value,
      litFacets:lit,glow:uniforms.uGlow.value,dim:uniforms.uDim.value};},
  };
}
