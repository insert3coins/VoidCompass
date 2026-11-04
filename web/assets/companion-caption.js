(() => {
  "use strict";
  const STANDARD_TYPING = {base: 26, spread: 26, stop: 300, comma: 130, hesitate: .04, pause: 160, think: 0, typos: 0, corrects: true, eager: 1};
  const NATURE_TYPING = {
    weary: {...STANDARD_TYPING, base: 40, spread: 32, stop: 520, comma: 220, hesitate: .08, pause: 280, think: 300},
    stoic: {...STANDARD_TYPING, base: 30, spread: 8, stop: 320, comma: 140, hesitate: 0, pause: 0, corrects: false},
    nervous: {...STANDARD_TYPING, base: 18, spread: 22, stop: 230, comma: 90, hesitate: .07, pause: 140, think: -120, typos: .06},
    curious: {...STANDARD_TYPING, base: 24, spread: 24, hesitate: .03, eager: .55},
  };
  // A beat before bad news: the eye has already seen it.
  const MOOD_BEAT = {wary: 450, downcast: 250};
  // A slip of the finger: the key beside the one it meant.
  const KEY_ROWS = ["qwertyuiop", "asdfghjkl", "zxcvbnm"];
  function neighbour(ch, roll) {
    const lower = ch.toLowerCase();
    const row = KEY_ROWS.find((keys) => keys.includes(lower));
    if (!row) return "";
    const at = row.indexOf(lower);
    const other = row[at + (roll < .5 && at > 0 ? -1 : at < row.length - 1 ? 1 : -1)];
    return ch === lower ? other : other.toUpperCase();
  }

  // A script's words: "[[typed|final]]" resolved, and the words it noticed
  // ("⟦Hatchooe⟧", from the journal) flagged. [{ch, noticed}] per character.
  function splitNoticed(text) {
    const out = [];
    for (const part of String(text).split(/(⟦[^⟧]*⟧)/)) {
      const noticed = part.startsWith("⟦") && part.endsWith("⟧");
      for (const ch of noticed ? part.slice(1, -1) : part) out.push({ch, noticed});
    }
    return out;
  }
  const finalWords = (script) => splitNoticed(String(script).replace(/\[\[([^|\]]*)\|([^\]]*)\]\]/g, "$2"));

  // How a thought is typed (5.5.3.2): unevenly, a pause after a comma and
  // a longer one after a full stop, and "[[typed|final]]" typed, stopped,
  // deleted and corrected; since 5.5.3.5 in its nature's own way. Returns
  // [{parts, ms}] frames (the words so far) and the total time.
  function typingPlan(script, nature, spoken = false) {
    const base = NATURE_TYPING[nature === "officer" ? "stoic" : nature] || STANDARD_TYPING;
    const feel = spoken ? {...base, typos: 0, corrects: false, hesitate: 0} : base;
    const frames = [];
    const shown = [];
    let total = 0;
    let seed = 0;
    for (const ch of String(script)) seed = (seed * 31 + ch.charCodeAt(0)) >>> 0;
    const next = () => ((seed = (seed * 1103515245 + 12345) >>> 0) / 4294967296);
    const push = (ms) => { frames.push({parts: shown.slice(), ms}); total += ms; };
    const typeOne = (ch, noticed) => {
      const last = shown.length ? shown[shown.length - 1].ch : "";
      const wordStart = !last || last === " ";
      if (wordStart && feel.typos && /[a-z]/i.test(ch) && next() < feel.typos) {
        const slip = neighbour(ch, next());
        if (slip) {
          shown.push({ch: slip, noticed});
          push(feel.base + next() * feel.spread);
          frames[frames.length - 1].ms += 160 + next() * 120;  // it sees it
          shown.pop();
          push(60);
        }
      }
      let ms = (feel.base + next() * feel.spread) * (noticed ? feel.eager : 1);
      if (last && ".!?".includes(last) && ch === " ") ms += feel.stop * (1 + next() * .7);
      else if (last && ",;:".includes(last) && ch === " ") ms += feel.comma * (1 + next() * .7);
      else if (last === " " && next() < feel.hesitate) ms += feel.pause;  // a small hesitation
      shown.push({ch, noticed});
      push(ms);
    };
    const type = (text) => { for (const {ch, noticed} of splitNoticed(text)) typeOne(ch, noticed); };
    for (const part of String(script).split(/(\[\[[^|\]]*\|[^\]]*\]\])/)) {
      const fix = /^\[\[([^|\]]*)\|([^\]]*)\]\]$/.exec(part);
      if (!fix) { type(part); continue; }
      if (!feel.corrects) { type(fix[2]); continue; }
      const before = shown.length;
      type(fix[1]);
      frames[frames.length - 1].ms += 380;  // it stops, and thinks better of it
      while (shown.length > before) {
        shown.pop();
        push(45);
      }
      frames[frames.length - 1].ms += 200;
      type(fix[2]);
    }
    return {frames, total};
  }

  function paintParts(target, parts) {
    const nodes = [];
    let run = "";
    let noticed = false;
    const flush = () => {
      if (!run) return;
      if (noticed) {
        const mark = document.createElement("em");
        mark.className = "noticed";
        mark.textContent = run;
        nodes.push(mark);
      } else {
        nodes.push(document.createTextNode(run));
      }
      run = "";
    };
    for (const part of parts) {
      if (part.noticed !== noticed) { flush(); noticed = part.noticed; }
      run += part.ch;
    }
    flush();
    target.replaceChildren(...nodes);
  }


  function createPresenter({paint, onDone=()=>{}, onThink=()=>{}, onStart=()=>{}, now=()=>performance.now()} = {}) {
    let timer=0, current=null, options={}, key='', scope='', input=null, received=0, visible=true;
    let lastLive=null, lastReceived=0, asked=0, due=0, naturalStart=null, heard=false, started=false, complete=true;
    let words=[],plan={frames:[],total:0},timeline=[],lastPaint='',voicePosition=0;
    const schedule=ms=>{clearTimeout(timer);timer=visible?setTimeout(tick,ms):0;};
    function draw(parts){
      const signature=parts.map(part=>(part.noticed?'1':'0')+part.ch).join('');
      if(signature!==lastPaint){lastPaint=signature;paint(parts);}
    }
    function finish(){draw(words);complete=true;clearTimeout(timer);timer=0;onDone(true);}
    function at(position){
      let low=0,high=timeline.length;
      while(low<high){const mid=(low+high)>>>1;if(timeline[mid]<=position)low=mid+1;else high=mid;}
      return low?plan.frames[low-1].parts:[];
    }
    function start(voiced,duration){if(!started){started=true;onStart(duration,voiced);}}
    function typeNaturally(time){
      if(naturalStart===null){naturalStart=time;start(false,plan.total);}
      const elapsed=time-naturalStart;
      if(options.reduced || elapsed>=plan.total){finish();return;}
      draw(at(elapsed));schedule(24);
    }
    function tick(){
      timer=0;if(!current||complete||!visible)return;
      const time=now();
      if(!current.voice){if(heard&&current.voice_full){finish();return;}if(time<due){schedule(Math.min(60,due-time));return;}typeNaturally(time);return;}
      if(naturalStart!==null){typeNaturally(time);return;}
      const status=current.voice_state || 'unknown';
      const live=input && String(input.key)===String(current.id) && time-received<500 ? input : null;
      if(live){lastLive=live;lastReceived=received;heard=true;start(true,Math.max(0,(live.duration-live.elapsed)*1000));}
      if(current.voice_full && status==='finished'){finish();return;}
      if(status==='failed'||status==='cancelled'){if(heard){finish();return;}typeNaturally(time);return;}
      if(heard && lastLive && current.voice_full){
        if(options.reduced){finish();return;}
        const duration=Math.max(.001,Number(lastLive.duration)||.001);
        const elapsed=Math.max(0,Number(lastLive.elapsed)||0)+Math.min(.25,Math.max(0,time-lastReceived)/1000);
        const progress=Math.min(1,elapsed/duration);
        voicePosition=Math.max(voicePosition,progress*plan.total);
        draw(at(voicePosition));
        const expectedEnd=lastReceived+(duration-(Number(lastLive.elapsed)||0))*1000;
        if(progress>=1 || (!live && time>=expectedEnd+250)){finish();return;}
        schedule(24);return;
      }
      if(live){typeNaturally(time);return;}
      if(['queued','preparing','playing'].includes(status) || (status!=='finished' && time-asked<3500)){
        schedule(60);return;
      }
      typeNaturally(time);
    }
    return {
      show(thought, nextOptions={}){
        const nextScope=`${nextOptions.scope||''}:${thought?.scope||''}`;
        const nextKey=thought?`${nextScope}:${thought.id}:${thought.script||thought.text}`:'';
        options=nextOptions;
        if(current && nextKey===key){current=thought;if(!complete&&!timer)schedule(0);return false;}
        clearTimeout(timer);timer=0;
        if(nextScope!==scope){input=null;lastLive=null;}
        scope=nextScope;key=nextKey;current=thought;complete=!thought;onDone(complete);
        lastLive=null;lastReceived=0;heard=false;started=false;naturalStart=null;voicePosition=0;
        lastPaint='\u0000';draw([]);
        if(!thought)return true;
        words=finalWords(thought.script||thought.text||'');
        plan={frames:[],total:0};timeline=[];
        if(options.instant || (options.reduced&&!thought.voice)){finish();return true;}
        plan=typingPlan(thought.script||thought.text||'',options.nature,Boolean(thought.voice_full));
        let sum=0;timeline=plan.frames.map(frame=>{const start=sum;sum+=frame.ms;return start;});
        const feel=NATURE_TYPING[options.nature==='officer'?'stoic':options.nature]||STANDARD_TYPING;
        const pause=Math.max(200,420+Math.floor(Math.random()*480)+feel.think+(MOOD_BEAT[thought.mood]||0));
        asked=now();due=asked+pause;onThink(pause);
        schedule(thought.voice?Math.min(pause,300):pause);return true;
      },
      live(speech, sampleTime=now()){
        input=speech && Number.isFinite(Number(speech.elapsed)) && Number(speech.duration)>0 ? speech : null;
        received=sampleTime;
        if (!complete && current?.voice && input && String(input.key)===String(current.id)) schedule(0);
        else if (!complete&&!timer) schedule(0);
      },
      setVisible(value){visible=Boolean(value);if(!visible){clearTimeout(timer);timer=0;}else if(!complete&&!timer)schedule(0);},
      clear(){clearTimeout(timer);timer=0;current=null;key='';input=null;lastLive=null;words=[];plan={frames:[],total:0};timeline=[];complete=true;lastPaint='\u0000';draw([]);onDone(true);},
      busy(){return Boolean(current&&!complete);},
      destroy(){this.clear();},
    };
  }
  window.CompanionCaption=Object.freeze({typingPlan,finalWords,paintParts,createPresenter});
})();
