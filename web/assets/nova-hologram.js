import * as THREE from "../galactic_map/vendor/three.module.min.js";

// Nova (5.8.6): an illustrated face projected inside the shared bezel, not a
// built robot. Her frames are sprite sheets (web/assets/nova/, from
// tools/make_nova_frames.py); this layer picks the frame and the crew renderer
// draws it, on its own clock: no loop or timer of its own.
//
// - On watch she idles (idle); after a quiet spell she settles (idle-settled).
//   Listening, working, charging and alert each have their own loop.
// - Speaking shows the mouth frame for the real playback level (never the
//   microphone or queued text), with the blink layer laid over the eyes now and then.
// - A mood plays its expression: pleased a warm smile (or delight), curious a
//   curious look; wary and downcast hold their pose while the mood lasts, then
//   let it go. Going to alert, surprise first; out of it, reassurance.
// - Something happening on one side of the screen: she glances that way and
//   holds the look while it has her attention.
// - A sign-off, once said: goodnight, eyes closed until something new.
// - A faint projection: scan lines, a slow light band and, rarely, a flicker.
// Reduced motion holds a still face (an expression's held or middle frame).
const BASE = {idle: "idle", listening: "listening", working: "working", charging: "charging", alert: "alert"};
const MOOD_CLIPS = {joy: ["warm-smile", "delighted"], curious: ["curious"], worry: ["wary"], sad: ["downcast"]};
const SETTLE_S = 45;
const EAGER = ["idle", "mouth-levels"];
const SIZE = 1.96;

export function addNovaHologram(parent, uniforms, onChange = () => {}) {
  const base = new URL("./nova/", import.meta.url);
  const loader = new THREE.TextureLoader();
  loader.setCrossOrigin("anonymous");
  const sheets = new Map();
  let info = null, failed = false;

  function texture(name, file = `${name}.webp`) {
    if (sheets.has(name)) return sheets.get(name);
    const row = {texture: null, ready: false};
    sheets.set(name, row);
    loader.load(new URL(file, base).href, (loaded) => {
      loaded.colorSpace = THREE.SRGBColorSpace;
      loaded.flipY = false;
      loaded.generateMipmaps = false;
      loaded.minFilter = THREE.LinearFilter;
      loaded.magFilter = THREE.LinearFilter;
      row.texture = loaded; row.ready = true;
      onChange();
    }, undefined, () => { row.failed = true; });
    return row;
  }

  fetch(new URL("nova.json", base).href).then((reply) => reply.json()).then((data) => {
    info = data;
    for (const name of EAGER) texture(name);
    texture("blink-layer", "blink-layer.webp");
    onChange();
  }).catch(() => { failed = true; });

  const material = new THREE.ShaderMaterial({
    uniforms: {
      uSheet: {value: null}, uFrame: {value: new THREE.Vector4(0, 0, 1, 1)},
      uLayer: {value: null}, uLayerFrame: {value: new THREE.Vector4(0, 0, 1, 1)}, uLayerRect: {value: new THREE.Vector4(0, 0, 0, 0)},
      uLayerOn: {value: 0}, uShow: {value: 0}, uTime: uniforms.uTime, uColour: uniforms.uColour, uEnergy: uniforms.uEnergy,
      uGlitch: {value: 0}, uProjection: {value: 1},
    },
    vertexShader: `varying vec2 vUv;void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}`,
    fragmentShader: `varying vec2 vUv;uniform sampler2D uSheet,uLayer;uniform vec4 uFrame,uLayerFrame,uLayerRect;
      uniform float uLayerOn,uShow,uTime,uEnergy,uGlitch,uProjection;uniform vec3 uColour;
      void main(){
        vec2 uv=vUv;
        // A rare projection fault: one thin band slips sideways for a moment.
        float band=step(abs(uv.y-fract(uTime*.37+.2)),.018)*uGlitch;
        uv.x+=band*.012;
        vec2 face=vec2(uv.x,1.0-uv.y);
        vec4 colour=texture2D(uSheet,uFrame.xy+clamp(face,0.0,1.0)*uFrame.zw);
        if(uLayerOn>.5){
          vec2 inRect=(face-uLayerRect.xy)/uLayerRect.zw;
          if(all(greaterThanEqual(inRect,vec2(0.0)))&&all(lessThanEqual(inRect,vec2(1.0)))){
            vec4 eyes=texture2D(uLayer,uLayerFrame.xy+inRect*uLayerFrame.zw);
            colour=vec4(mix(colour.rgb,eyes.rgb,eyes.a),max(colour.a,eyes.a));
          }
        }
        if(colour.a<.003)discard;
        // The projection: fine scan lines, a slow band of light, her palette at the edges.
        float lines=.95+.05*sin(gl_FragCoord.y*2.2);
        float sweep=exp(-pow((face.y-fract(uTime*.11))/.05,2.0));
        vec3 tint=mix(colour.rgb,colour.rgb*.86+uColour*.22,uProjection*.35);
        tint+=uColour*sweep*.07*uProjection+uColour*uEnergy*.04;
        float alpha=colour.a*mix(1.0,lines,uProjection)*(1.0-band*.35)*uShow;
        gl_FragColor=vec4(tint,alpha);
        #include <colorspace_fragment>
      }`,
    transparent: true, depthWrite: false, depthTest: false, blending: THREE.NormalBlending,
  });
  const plane = new THREE.Mesh(new THREE.PlaneGeometry(SIZE, SIZE), material);
  plane.name = "nova-hologram"; plane.renderOrder = 1; plane.position.z = .1;
  parent.add(plane);

  let clip = "idle", frame = 0, clock = 0, once = null, lastMood = "", lastState = "idle", lastThought = null;
  let joyTurn = 0, blinkAt = 3.2, blinkClock = -1, glitchAt = 18, glitch = 0, shown = "", show = 0, busy = false;
  let quiet = 0, night = "", live = {pose: {}};   // night: "" awake, "due" after a sign-off, "asleep" eyes closed

  function setFrame(uniform, row, index, cols) {
    const rows = Math.ceil(row.frames / cols);
    uniform.set((index % cols) / cols, Math.floor(index / cols) / rows, 1 / cols, 1 / rows);
  }

  function ready(name) { return Boolean(info?.clips[name]) && texture(name).ready; }

  function moodOf(expression) {
    let best = "", most = .35;
    for (const key of ["worry", "sad", "joy", "curious"]) if (expression[key] > most) { best = key; most = expression[key]; }
    return best;
  }

  // An expression to play: held at its pose while keep() says so, then released.
  function play(name, keep = () => false) {
    once = {name, clock: 0, keep, hold: info.clips[name]?.hold ?? null};
  }

  // The frame an expression is on, or null once it has finished.
  function playing(dt, speed, reduced) {
    const row = info.clips[once.name];
    const held = once.hold !== null && once.keep();
    if (reduced) return held ? once.hold : once.keep() ? Math.floor(row.frames / 2) : null;
    const at = Math.floor(once.clock * (row.fps || 15));
    if (held && at >= once.hold) { once.clock = once.hold / (row.fps || 15); return once.hold; }
    once.clock += dt * speed;
    const next = Math.floor(once.clock * (row.fps || 15));
    return next >= row.frames ? null : next;
  }

  return {
    update({dt = 0, state = "idle", mouthOpen = 0, reduced = false, animated = true, expression = {}, activity = 1, pose = {},
            focus = "tracking", thought = null}) {
      live.pose = pose;
      if (!info) { busy = !failed; return; }
      const speed = Math.sqrt(Math.max(.25, activity));
      const mood = moodOf(expression);
      const speaking = state === "speaking";
      const fresh = thought && thought.id !== lastThought;
      if (fresh) {
        lastThought = thought.id;
        if (night === "asleep" || night === "due") night = "";
        if (/^sign_off/.test(String(thought.topic || ""))) night = "due";
      }
      if (state !== "idle" && !speaking && night === "asleep") night = "";
      // What starts an expression.
      // Surprise and reassurance play out before a new mood shows.
      const steady = once && (once.name === "surprised" || once.name === "reassuring");
      if (state === "alert" && lastState !== "alert") play("surprised");
      else if (lastState === "alert" && state === "idle") play("reassuring");
      else if (state !== "alert" && !steady && mood && mood !== lastMood && MOOD_CLIPS[mood]) {
        const options = MOOD_CLIPS[mood];
        play(options[(mood === "joy" ? joyTurn++ : 0) % options.length], () => moodOf(expression) === mood);
      } else if (!once && !night && state === "idle" && !reduced && focus !== "off" && pose.attention > 0 && Math.abs(pose.x || 0) > .3) {
        // Toward the side of the screen something happened on (the viewer's left or right).
        play(pose.x > 0 ? "glance-right" : "glance-left", () => live.pose.attention > 0);
      } else if (night === "due" && !speaking && !once) {
        night = "asleep";
        play("goodnight", () => night === "asleep");
      }
      if (!steady || state === "alert") lastMood = mood;
      lastState = state;
      // Settled after a quiet spell on watch.
      quiet = state === "idle" && !once && !mood && !(pose.attention > 0) ? quiet + dt : 0;
      let name, index;
      if (speaking && ready("mouth-levels")) {
        // Speech wins: the mouth follows the voice. An expression waits.
        const levels = info.clips["mouth-levels"].frames;
        name = "mouth-levels"; index = reduced ? 0 : Math.max(0, Math.min(levels - 1, Math.round(mouthOpen * (levels - 1))));
      } else if (once) {
        if (!ready(once.name)) texture(once.name);
        else {
          const at = playing(dt, speed, reduced);
          if (at === null) once = null;
          else { name = clip = once.name; index = at; }
        }
      }
      if (!name) {
        const want = state === "idle" && quiet >= SETTLE_S && ready("idle-settled") ? "idle-settled" : BASE[state] || "idle";
        name = ready(want) ? want : "idle";
        if (!ready(want)) texture(want);
        if (state === "idle") texture("idle-settled");
        const row = info.clips[name];
        if (name !== clip) { clip = name; clock = 0; }
        if (animated && !reduced) clock += dt * speed;
        index = reduced ? 0 : Math.floor(clock * (row.fps || 15)) % row.frames;
      }
      const sheet = texture(name);
      if (!sheet.ready) { busy = true; return; }
      material.uniforms.uSheet.value = sheet.texture;
      setFrame(material.uniforms.uFrame.value, info.clips[name], index, info.clips[name].cols);
      frame = index; shown = name;
      // The blink layer over speech, every few seconds.
      const layer = info.layer, eyes = sheets.get("blink-layer");
      material.uniforms.uLayerOn.value = 0;
      if (speaking && !reduced && eyes?.ready) {
        blinkAt -= dt;
        if (blinkClock < 0 && blinkAt <= 0) { blinkClock = 0; blinkAt = 2.6 + Math.random() * 2.8; }
        if (blinkClock >= 0) {
          const step = Math.floor(blinkClock * layer.fps);
          blinkClock += dt;
          if (step >= layer.frames) blinkClock = -1;
          else if (!layer.skip.includes(step)) {
            material.uniforms.uLayer.value = eyes.texture;
            setFrame(material.uniforms.uLayerFrame.value, layer, step, layer.cols);
            material.uniforms.uLayerRect.value.set(...layer.rect);
            material.uniforms.uLayerOn.value = 1;
          }
        }
      } else blinkClock = -1;
      // Now and then, a flicker in the projection.
      glitch = Math.max(0, glitch - dt * 6);
      if (animated && !reduced) { glitchAt -= dt; if (glitchAt <= 0) { glitch = 1; glitchAt = 16 + Math.random() * 22; } }
      else glitch = 0;
      material.uniforms.uGlitch.value = glitch;
      material.uniforms.uProjection.value = reduced ? .4 : 1;
      // Fades in the first time her frames arrive; drifts a touch with attention.
      show = reduced ? 1 : Math.min(1, show + dt * 3);
      material.uniforms.uShow.value = show;
      const tracking = !reduced && focus !== "off";
      plane.position.x = tracking ? (pose.x || 0) * .018 : 0;
      plane.position.y = tracking ? (pose.y || 0) * .014 : 0;
      // A held pose waits on the mood or attention that holds it; asleep, nothing moves.
      const sleeping = night === "asleep" && once?.name === "goodnight" && frame === once.hold;
      busy = (Boolean(once) && !sleeping) || night === "due" || blinkClock >= 0 || glitch > 0 || show < 1;
    },
    get busy() { return busy; },
    inspect() {
      return {design: "projected-android", clip: shown, frame, expressionClip: once?.name || null, blinking: blinkClock >= 0, night, quiet,
        glitch, loaded: [...sheets].filter(([, row]) => row.ready).map(([key]) => key), ready: Boolean(info), failed};
    },
    destroy() {
      for (const row of sheets.values()) row.texture?.dispose();
      sheets.clear();
    },
  };
}
