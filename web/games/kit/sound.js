// The cabinets' sound: small synthesised blips and loops, nothing to
// download. Nothing plays until the player has pressed something, as the
// browser asks.
(() => {
  "use strict";
  const Kit = window.Kit = window.Kit || {};

  Kit.sound = function sound(volume = .2) {
    let audio = null, master = null, noise = null, muted = false;

    function ready() {
      if (audio) {
        if (audio.state === "suspended") audio.resume().catch(() => {});
        return;
      }
      const Context = window.AudioContext || window.webkitAudioContext;
      if (!Context) return;
      audio = new Context();
      master = audio.createGain();
      master.gain.value = muted ? 0 : volume;
      master.connect(audio.destination);
      noise = audio.createBuffer(1, audio.sampleRate, audio.sampleRate);
      const data = noise.getChannelData(0);
      for (let index = 0; index < data.length; index += 1) data[index] = Math.random() * 2 - 1;
    }

    function tone(type, from, to, length, level = .5, delay = 0) {
      if (!audio || muted) return;
      const at = audio.currentTime + delay;
      const osc = audio.createOscillator(), gain = audio.createGain();
      osc.type = type;
      osc.frequency.setValueAtTime(from, at);
      osc.frequency.exponentialRampToValueAtTime(Math.max(20, to), at + length);
      gain.gain.setValueAtTime(level, at);
      gain.gain.exponentialRampToValueAtTime(.001, at + length);
      osc.connect(gain).connect(master);
      osc.start(at);
      osc.stop(at + length + .02);
    }

    function hiss(length, level = .5, cutoff = 1800, delay = 0) {
      if (!audio || muted) return;
      const at = audio.currentTime + delay;
      const source = audio.createBufferSource();
      source.buffer = noise;
      const filter = audio.createBiquadFilter();
      filter.type = "lowpass";
      filter.frequency.setValueAtTime(cutoff, at);
      filter.frequency.exponentialRampToValueAtTime(80, at + length);
      const gain = audio.createGain();
      gain.gain.setValueAtTime(level, at);
      gain.gain.exponentialRampToValueAtTime(.001, at + length);
      source.connect(filter).connect(gain).connect(master);
      source.start(at);
      source.stop(at + length + .02);
    }

    function note(type, frequency, at, length, level) {
      const osc = audio.createOscillator(), gain = audio.createGain();
      osc.type = type;
      osc.frequency.setValueAtTime(frequency, at);
      gain.gain.setValueAtTime(0, at);
      gain.gain.linearRampToValueAtTime(level, at + .01);
      gain.gain.setValueAtTime(level, at + Math.max(.012, length - .04));
      gain.gain.linearRampToValueAtTime(0, at + length);
      osc.connect(gain).connect(master);
      osc.start(at);
      osc.stop(at + length + .02);
    }

    // A looping tune. Each part is a wave, a level and a row of steps: a
    // midi note number, or null for a rest; a step lasts `step` beats.
    function track({bpm = 120, step = .25, parts = []}) {
      const length = Math.max(...parts.map((part) => part.notes.length));
      let timer = 0, next = 0, index = 0;
      const seconds = 60 / bpm * step;
      function schedule() {
        if (!audio) return;
        while (next < audio.currentTime + .2) {
          if (!muted) {
            for (const part of parts) {
              const value = part.notes[index % part.notes.length];
              if (value === null || value === undefined) continue;
              const hold = (part.hold || 1) * seconds * .92;
              note(part.wave || "square", 440 * 2 ** ((value - 69) / 12), next, hold, part.level ?? .1);
            }
          }
          next += seconds;
          index = (index + 1) % length;
        }
      }
      return {
        play() {
          ready();
          if (timer || !audio) return;
          next = audio.currentTime + .05;
          timer = setInterval(schedule, 50);
          schedule();
        },
        stop() { clearInterval(timer); timer = 0; },
        restart() { index = 0; },
        get playing() { return Boolean(timer); },
      };
    }

    return {
      ready, tone, hiss, track,
      mute(on) { muted = Boolean(on); if (master) master.gain.value = muted ? 0 : volume; },
      get muted() { return muted; },
    };
  };
})();
