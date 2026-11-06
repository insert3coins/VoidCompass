import * as THREE from "../galactic_map/vendor/three.module.min.js";

export const COMPANION_EXTENT = 1.16;

// A physical silhouette for the holograms, like the Watcher's instrument
// housing. Normal blending gives it contrast over bright game scenery;
// luminous detail in the companion's own renderer is still additive.
// 5.7.6: each officer's own bezel, inside the same silhouette (the same size
// for all): "command" (Aster: six notches, rank chevrons at the top), "scale"
// (Axiom: a graduated measuring scale), "compass" (Meridian: a brass rose
// with cardinal points). Anything else is the plain shared bezel.
const STYLES = {command:1, scale:2, compass:3};
export function createCompanionFrame({colour, energy, opening = .30, style = ""}) {
  const material = front => new THREE.ShaderMaterial({
    uniforms: {uColour:colour, uEnergy:energy, uOpening:{value:opening}, uFront:{value:front?1:0}, uStyle:{value:STYLES[style]||0}},
    vertexShader: `varying vec2 vUv;
      void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}`,
    fragmentShader: `varying vec2 vUv;uniform vec3 uColour;uniform float uEnergy,uOpening,uFront,uStyle;
      float stroke(float d,float width){return 1.0-smoothstep(width,width+fwidth(d),abs(d));}
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
        }else if(uStyle>2.5){
          // Compass: cardinal points as long triangles, intercardinals shorter, and a fine rose.
          float d=abs(fract(turn*4.0+.5)-.5)*1.5707963*r;
          float spread=.03*clamp((1.13-r)/.09,0.0,1.0);
          float cardinal=(1.0-smoothstep(spread-.004,spread,d))*step(1.04,r)*(1.0-step(1.13,r));
          float inter=(1.0-step(.04,abs(fract(turn*8.0+.5)-.5)))*stroke(r-1.075,.02);
          float rose=(1.0-step(.08,fract(turn*32.0)))*stroke(r-1.095,.008);
          ticks=max(max(cardinal,inter),rose*.8);
        }
        float alpha=uFront>.5?max(housing*.96*edge,bevel*.94):glass*.76;
        if(alpha<.001)discard;
        vec3 dark=vec3(.012,.022,.032);
        vec3 steel=mix(vec3(.065,.10,.13),vec3(.24,.31,.36),sheen);
        // Meridian's bezel is brass.
        if(uStyle>2.5)steel=mix(vec3(.12,.085,.035),vec3(.46,.35,.17),sheen);
        vec3 surface=dark;
        if(uFront>.5){
          surface=mix(dark,steel,housing);
          surface=mix(surface,dark,inset*.7);
          surface=mix(surface,mix(uColour,vec3(.83,.92,.97),.32),clamp(bevel*(.72+sheen*.28)+ticks*.42,0.0,1.0));
          surface+=uColour*bevel*clamp(uEnergy,0.0,1.0)*.12;
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
