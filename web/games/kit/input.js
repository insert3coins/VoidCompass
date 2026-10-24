// Keys, mouse and touch for a cabinet, in game units. The deck can ask for
// keys only (the mouse neither steers nor fires) or mouse only (the keys
// neither steer nor fire); the cabinet's own keys (pause, sound, screen)
// and a click to start always work.
(() => {
  "use strict";
  const Kit = window.Kit = window.Kit || {};
  const SWALLOW = ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Space"];

  Kit.input = function input(canvas, width, height) {
    const keys = new Set();
    const pointer = {x: width / 2, y: height / 2, down: false, button: 0, active: false, clicks: 0};
    const handlers = {key: [], down: []};
    let mode = "both";

    function place(event) {
      const box = canvas.getBoundingClientRect();
      pointer.x = (event.clientX - box.left) / box.width * width;
      pointer.y = (event.clientY - box.top) / box.height * height;
    }

    window.addEventListener("keydown", (event) => {
      if (SWALLOW.includes(event.code)) event.preventDefault();
      if (event.repeat) return;
      if (handlers.key.some((handler) => handler(event.code, event) === true)) return;
      if (mode !== "mouse") keys.add(event.code);
    });
    window.addEventListener("keyup", (event) => keys.delete(event.code));
    canvas.addEventListener("pointermove", (event) => {
      place(event);
      if (mode !== "keys") pointer.active = true;
    });
    canvas.addEventListener("pointerdown", (event) => {
      window.focus();
      place(event);
      if (handlers.down.some((handler) => handler(event) === true)) return;
      if (mode === "keys") return;
      pointer.down = true;
      pointer.button = event.button;
      pointer.active = true;
      pointer.clicks += 1;
      canvas.setPointerCapture?.(event.pointerId);
    });
    window.addEventListener("pointerup", () => { pointer.down = false; });
    canvas.addEventListener("contextmenu", (event) => event.preventDefault());

    return {
      keys, pointer,
      held(...codes) { return codes.some((code) => keys.has(code)); },
      // A click since the last look, for games that act once per click.
      clicked() { const had = pointer.clicks > 0; pointer.clicks = 0; return had; },
      on(kind, handler) { handlers[kind].push(handler); },
      release() { keys.clear(); pointer.down = false; pointer.clicks = 0; },
      get mode() { return mode; },
      setMode(next) {
        mode = ["keys", "mouse"].includes(next) ? next : "both";
        if (mode === "keys") { pointer.active = false; pointer.down = false; pointer.clicks = 0; }
        if (mode === "mouse") keys.clear();
      },
    };
  };

  // The usual four ways of steering, for games that want a direction.
  Kit.LEFT = ["ArrowLeft", "KeyA"];
  Kit.RIGHT = ["ArrowRight", "KeyD"];
  Kit.UP = ["ArrowUp", "KeyW"];
  Kit.DOWN = ["ArrowDown", "KeyS"];
})();
