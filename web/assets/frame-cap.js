/* Overlay frame-rate cap (Overlay Studio > All overlays > Frame rate).

   Loaded first in every overlay page. Each overlay animates with
   requestAnimationFrame, which runs at the display's refresh rate (60, 144,
   240 Hz) in every overlay window at once, on top of the game. This wraps
   it so all of a page's animation loops share one paced frame: callbacks
   queued between frames run together at the chosen rate. 0 leaves the
   browser's own pacing alone. The rate arrives with each overlay's health
   poll as `frame_rate`. */
(function (global) {
  "use strict";

  const nativeRequest = global.requestAnimationFrame.bind(global);
  const nativeCancel = global.cancelAnimationFrame.bind(global);
  const queue = new Map();
  let interval = 1000 / 30;
  let last = 0;
  let handle = 0;
  let scheduled = false;

  function run(now) {
    scheduled = false;
    const due = last + interval - 1;
    if (now < due) {
      // Wait out the gap without waking every display refresh.
      scheduled = true;
      global.setTimeout(() => nativeRequest(run), Math.max(0, due - now - 2));
      return;
    }
    last = now;
    const callbacks = [...queue.values()];
    queue.clear();
    for (const callback of callbacks) {
      try {
        callback(now);
      } catch (error) {
        global.setTimeout(() => { throw error; });
      }
    }
  }

  global.requestAnimationFrame = (callback) => {
    if (!interval) return nativeRequest(callback);
    handle += 1;
    queue.set(handle, callback);
    if (!scheduled) {
      scheduled = true;
      nativeRequest(run);
    }
    // Negative handles are ours; the browser's are positive.
    return -handle;
  };

  global.cancelAnimationFrame = (id) => {
    if (id < 0) queue.delete(-id);
    else nativeCancel(id);
  };

  global.VoidCompassFrameCap = Object.freeze({
    set(framesPerSecond) {
      const fps = Number(framesPerSecond);
      interval = Number.isFinite(fps) && fps > 0 ? 1000 / Math.max(5, Math.min(240, fps)) : 0;
    },
  });
})(window);
