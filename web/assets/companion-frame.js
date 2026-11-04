import * as THREE from "../galactic_map/vendor/three.module.min.js";

export const COMPANION_EXTENT = 1.16;

// A physical silhouette for the holograms, like the Watcher's instrument
// housing. Normal blending gives it contrast over bright game scenery;
// luminous detail in the companion's own renderer is still additive.
export function createCompanionFrame({colour, energy, opening = .30}) {
  const material = front => new THREE.ShaderMaterial({
    uniforms: {uColour:colour, uEnergy:energy, uOpening:{value:opening}, uFront:{value:front?1:0}},
    vertexShader: `varying vec2 vUv;
      void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}`,
    fragmentShader: `varying vec2 vUv;uniform vec3 uColour;uniform float uEnergy,uOpening,uFront;
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
        float ticks=stroke(r-1.079,.023)*(1.0-step(.075,fract((a+3.14159265)/6.2831853*48.0)));
        float alpha=uFront>.5?max(housing*.96*edge,bevel*.94):glass*.76;
        if(alpha<.001)discard;
        vec3 dark=vec3(.012,.022,.032);
        vec3 steel=mix(vec3(.065,.10,.13),vec3(.24,.31,.36),sheen);
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
