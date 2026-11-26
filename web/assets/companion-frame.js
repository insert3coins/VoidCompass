import * as THREE from "../galactic_map/vendor/three.module.min.js";

export const COMPANION_EXTENT = 1.16;

// A physical silhouette for the holograms, like the Watcher's instrument
// housing. Normal blending gives it contrast over bright game scenery;
// luminous detail in the companion's own renderer is still additive.
// 5.7.6: each officer's own bezel, inside the same silhouette (the same size
// for all): "command" (Aster: six notches, rank chevrons at the top), "scale"
// (Axiom: a graduated measuring scale), "compass" (Meridian: a brass rose
// with cardinal points). 5.8.6: "nova" (Nova: pearl, a lit ring at each temple
// like hers and a four-point star at the top). Anything else is the plain shared bezel.
// 5.8.6: the pets' rings are animated, on the display's own clock: "gyro"
// (Parallax: two gimbal rings crossing at her collar's pivots, turning on their
// axes, glow arcs top and bottom) and "collar" (Rivet: a riveted strap with
// copper plates turning slowly, teal markers and a receiver's sweeping track).
const STYLES = {command:1, scale:2, compass:3, nova:4, gyro:5, collar:6};
// 5.7.7: your standing with the officer (Crew Orders), as service pips set
// into the bottom of the bezel: one for Trusted up to four for Indispensable,
// the fourth gilding them all. Inside the same silhouette, so no display grows.
export function createCompanionFrame({colour, energy, opening = .30, style = "", service = {value:0}, time = {value:0}}) {
  const material = front => new THREE.ShaderMaterial({
    uniforms: {uColour:colour, uEnergy:energy, uOpening:{value:opening}, uFront:{value:front?1:0}, uStyle:{value:STYLES[style]||0},
      uService:service, uTime:time},
    vertexShader: `varying vec2 vUv;
      void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}`,
    fragmentShader: `varying vec2 vUv;uniform vec3 uColour;uniform float uEnergy,uOpening,uFront,uStyle,uService,uTime;
      float stroke(float d,float width){return 1.0-smoothstep(width,width+fwidth(d),abs(d));}
      // Distance (in arc, roughly) from an angle to a mark at another.
      float arcTo(float a,float b){return abs(mod(a-b+3.14159265,6.2831853)-3.14159265);}
      void main(){
        vec2 p=(vUv-.5)*2.55;float r=length(p),a=atan(p.y,p.x);
        float edge=1.0-smoothstep(1.125,1.155,r);
        if(edge<=0.0)discard;
        float aperture=uOpening>0.0?smoothstep(uOpening,uOpening+.055,r):1.0;
        float glass=aperture*(1.0-smoothstep(1.035,1.065,r));
        float housing=smoothstep(1.015,1.035,r)*(1.0-smoothstep(1.115,1.135,r));
        float bevel=stroke(r-1.105,.009)+stroke(r-1.037,.005)*.65;
        float inset=stroke(r-1.074,.016);
        float sheen=pow(.5+.5*cos(a-2.2),5.0);
        float turn=fract((a+3.14159265)/6.2831853);
        float ticks=stroke(r-1.079,.023)*(1.0-step(.075,fract(turn*48.0)));
        if(uStyle>.5&&uStyle<1.5){
          // Command: six deep notches, and three rank chevrons at the top.
          ticks=stroke(r-1.079,.03)*(1.0-step(.05,fract(turn*6.0+.5)));
          float c=0.0;
          for(int i=0;i<3;i++){float k=float(i)-1.0;vec2 m=p-vec2(k*.1,1.082);
            c+=stroke(m.y+abs(m.x)*.75-.02,.009)*(1.0-step(.045,abs(m.x)));}
          ticks=max(ticks,c*1.4);
        }else if(uStyle>1.5&&uStyle<2.5){
          // Scale: fine graduations, longer every fifth, longest every tenth.
          float fine=1.0-step(.16,fract(turn*120.0));
          float five=1.0-step(.08,fract(turn*24.0));
          float ten=1.0-step(.06,fract(turn*12.0));
          ticks=stroke(r-1.09,.012)*fine*.8+stroke(r-1.08,.022)*five+stroke(r-1.075,.03)*ten;
        }else if(uStyle>3.5&&uStyle<4.5){
          // Nova: a ring at each temple (3 and 9 o'clock), a four-point star at the top, fine dots between.
          float rings=0.0;
          for(int i=0;i<2;i++){vec2 c=vec2(float(i)*2.0-1.0,0.0)*1.079;float d=length(p-c);
            rings=max(rings,stroke(d-.034,.008)+ (1.0-smoothstep(.012,.016,d))*.8);}
          vec2 q=p-vec2(0.0,1.079);
          float star=1.0-smoothstep(.0,.006,min(abs(q.x)*14.0+abs(q.y),abs(q.y)*14.0+abs(q.x))-.05);
          float dots=(1.0-step(.06,fract(turn*64.0)))*stroke(r-1.079,.006);
          ticks=max(max(rings,star*1.3),dots*.6);
        }else if(uStyle>2.5){
          // Compass: cardinal points as long triangles, intercardinals shorter, and a fine rose.
          float d=abs(fract(turn*4.0+.5)-.5)*1.5707963*r;
          float spread=.03*clamp((1.13-r)/.09,0.0,1.0);
          float cardinal=(1.0-smoothstep(spread-.004,spread,d))*step(1.04,r)*(1.0-step(1.13,r));
          float inter=(1.0-step(.04,abs(fract(turn*8.0+.5)-.5)))*stroke(r-1.075,.02);
          float rose=(1.0-step(.08,fract(turn*32.0)))*stroke(r-1.095,.008);
          ticks=max(max(cardinal,inter),rose*.8);
        }
        // Service pips: small studs across the bottom of the housing.
        float pips=0.0;
        for(int i=0;i<4;i++){
          float k=float(i);
          if(k<uService){
            vec2 c=vec2((k-(min(uService,4.0)-1.0)*.5)*.085,-1.079);
            pips=max(pips,1.0-smoothstep(.016,.016+fwidth(length(p-c))*1.5,length(p-c)));
          }
        }
        float alpha=uFront>.5?max(housing*.96*edge,bevel*.94):glass*.76;
        // The pets' rings: their own colour and coverage, drawn instead of the steel housing.
        vec3 ringColour=vec3(0.0);float ringAlpha=0.0;
        if(uStyle>4.5&&uStyle<5.5){
          // Parallax's gyroscope collar, all of it on the bezel band (r 1.04 to 1.125),
          // bold enough to read at small sizes: a dark band; the teal gimbal on its
          // inner half and the violet on its outer half, pinching in to meet at the
          // pivot bearings at 3 and 9 o'clock. Each gimbal is broken into segments
          // that turn its own way, breathes as it tips, and carries a rotor bead.
          // Colours are mixed, never added, so they stay teal and violet.
          float band=smoothstep(1.036,1.046,r)*(1.0-smoothstep(1.118,1.128,r));
          vec3 col=mix(vec3(.028,.040,.075),vec3(.060,.075,.125),sheen*.6);
          col=mix(col,vec3(.22,.25,.40),clamp(stroke(r-1.042,.003)+stroke(r-1.121,.003),0.0,1.0)*.8);
          float s=abs(sin(a)),glow=0.0;
          for(int i=0;i<2;i++){
            float k=float(i),side=k<.5?-1.0:1.0;
            float th=k<.5?uTime*.6:-uTime*.45+1.7;
            float d=r-(1.082+side*.025*s*(.78+.22*cos(th)));
            float core=stroke(d,.0062);
            float spin=uTime*side*.045+k*.5;
            float gap=step(.14,fract((a+3.14159265)/6.2831853*3.0+spin));
            float near=.55+.45*(.5+.5*sin(a+th));
            float bead=exp(-pow(arcTo(a,-uTime*side*1.1+k*3.14159265)/.07,2.0));
            vec3 hue=k<.5?vec3(.22,.88,.84):vec3(.60,.38,1.0);
            float v=clamp(core*gap*near+core*bead,0.0,1.0);
            col=mix(col,hue*(1.0+bead*.6),v);
            col+=hue*exp(-pow(d/.010,2.0))*gap*near*.18;
            glow=max(glow,v);
          }
          float arcs=exp(-pow((r-1.115)/.006,2.0))*smoothstep(.75,.99,s)*(.55+.45*sin(uTime*.8))*clamp(.65+uEnergy*.5,0.0,1.0);
          col=mix(col,vec3(.72,.58,1.0),arcs*.8);
          vec2 dq=vec2(abs(p.x)-1.082,p.y);
          float bearing=stroke(length(dq)-.030,.0055);
          float diamond=1.0-smoothstep(.0,.006,abs(dq.x)*1.4+abs(dq.y)-.022);
          col=mix(col,vec3(.62,.70,.90),bearing);
          col=mix(col,vec3(.82,.99,1.0),diamond);
          ringColour=col;ringAlpha=max(band,max(diamond,bearing))*edge;
        }else if(uStyle>5.5){
          // Rivet's collar: a dark segmented strap with gaps and tan edges, three copper
          // plates, all turning slowly; teal markers that stay put; a receiver's dashed
          // track inside, turning the other way with a brighter sweep.
          float spin=uTime*.05,b=a-spin;
          float turnB=fract((b+3.14159265)/6.2831853);
          float strap=smoothstep(1.036,1.046,r)*(1.0-smoothstep(1.118,1.128,r));
          float gaps=1.0;
          for(int i=0;i<4;i++){float at=float(i)==0.0?.08:float(i)==1.0?.31:float(i)==2.0?.63:.82;gaps*=step(.018,abs(turnB-at));}
          strap*=gaps;
          float seam=step(.86,fract(turnB*90.0));
          float rim=stroke(r-1.044,.004)+stroke(r-1.12,.004);
          vec3 band=mix(vec3(.10,.145,.15),vec3(.05,.07,.075),seam);
          band=mix(band,vec3(.58,.52,.40),clamp(rim,0.0,1.0)*.85);
          float plate=0.0,hatch=0.0,rivet=0.0;
          for(int i=0;i<3;i++){
            float at=float(i)==0.0?.36:float(i)==1.0?3.5:5.5;
            float d=arcTo(b,at)*r;
            float on=(1.0-smoothstep(.085,.092,d))*smoothstep(1.046,1.052,r)*(1.0-smoothstep(1.112,1.118,r));
            plate=max(plate,on);
            hatch=max(hatch,on*step(.72,fract((b-at)*40.0+(r-1.08)*55.0)));
            vec2 c1=vec2(cos(at+spin+.075),sin(at+spin+.075))*1.082,c2=vec2(cos(at+spin-.075),sin(at+spin-.075))*1.082;
            rivet=max(rivet,1.0-smoothstep(.008,.012,min(length(p-c1),length(p-c2))));
          }
          vec3 copper=mix(vec3(.80,.45,.19),vec3(.33,.16,.07),hatch);
          band=mix(band,copper,plate);
          band=mix(band,vec3(.97,.84,.64),rivet);
          ringColour=band;ringAlpha=max(strap,max(plate,rivet))*edge;
          float marks=0.0;
          for(int i=0;i<3;i++){
            float at=float(i)==0.0?-.12:float(i)==1.0?2.62:-1.57;
            vec2 m=p-vec2(cos(at),sin(at))*1.082;
            vec2 u=vec2(dot(m,vec2(cos(at),sin(at))),dot(m,vec2(-sin(at),cos(at))));
            marks=max(marks,1.0-smoothstep(.0,.006,abs(u.x)*1.6+abs(u.y)-.026));
          }
          float pulse=.65+.35*sin(uTime*1.4);
          ringColour=mix(ringColour,vec3(.55,.90,.76),marks);ringAlpha=max(ringAlpha,marks*pulse+marks*.0);
          float c=a+uTime*.18;
          float dash=step(.5,fract((c+3.14159265)/6.2831853*44.0))*stroke(r-.995,.004);
          float sweep=exp(-pow(arcTo(a,-uTime*.9)/.35,2.0));
          float track=dash*(.45+.55*sweep);
          ringColour=mix(ringColour,vec3(.42,.74,.66)+sweep*.25,track*(1.0-ringAlpha));
          ringAlpha=max(ringAlpha,track*.85);
        }
        if(uFront>.5&&uStyle>4.5){
          alpha=max(ringAlpha,housing*.32*edge);
        }
        if(alpha<.001)discard;
        vec3 dark=vec3(.012,.022,.032);
        vec3 steel=mix(vec3(.065,.10,.13),vec3(.24,.31,.36),sheen);
        // Meridian's bezel is brass.
        if(uStyle>2.5&&uStyle<3.5)steel=mix(vec3(.12,.085,.035),vec3(.46,.35,.17),sheen);
        // Nova's is pearl-silver, like her plates.
        if(uStyle>3.5)steel=mix(vec3(.16,.18,.23),vec3(.62,.66,.76),sheen);
        vec3 surface=dark;
        if(uFront>.5){
          surface=mix(dark,steel,housing);
          surface=mix(surface,dark,inset*.7);
          surface=mix(surface,mix(uColour,vec3(.83,.92,.97),.32),clamp(bevel*(.72+sheen*.28)+ticks*.42,0.0,1.0));
          surface+=uColour*bevel*clamp(uEnergy,0.0,1.0)*.12;
          vec3 pipColour=uService>3.5?vec3(1.0,.82,.42):mix(uColour,vec3(.95,.98,1.0),.35);
          surface=mix(surface,pipColour,pips*.95);
          if(uStyle>4.5)surface=mix(mix(dark,steel*.6,housing),ringColour,clamp(ringAlpha*1.2,0.0,1.0))+pipColour*pips*.9;
        }
        gl_FragColor=vec4(surface,alpha);
        #include <colorspace_fragment>
      }`,
    transparent:true, depthWrite:false, depthTest:false,
    blending:THREE.NormalBlending, side:THREE.DoubleSide, forceSinglePass:true,
  });
  const frame = new THREE.Group(), geometry = new THREE.PlaneGeometry(2.55,2.55);
  const recess = new THREE.Mesh(geometry,material(false));
  recess.renderOrder=-10;recess.position.z=-.8;
  const bezel = new THREE.Mesh(geometry,material(true));
  bezel.renderOrder=10;bezel.position.z=.8;
  frame.add(recess,bezel);
  frame.name="companion-contrast-frame";
  return frame;
}
