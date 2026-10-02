/* Overlay Studio layout mode (5.5.1.5).

   Most overlays show only when they have something to say, which made them
   hard to place. In layout mode the app shows every enabled overlay, and
   this draws each one's window as a labelled outline over whatever it shows
   (or over nothing), so it can be lined up from Overlay Studio. It arrives
   with each health poll as `layout` and the overlay's `title`. */
(function (global) {
  "use strict";

  let frame = null;

  function show(title) {
    if (!frame) {
      // A linked file: the overlay pages' policy blocks inline styles.
      const style = document.createElement("link");
      style.id = "vc-layout-style";
      style.rel = "stylesheet";
      style.href = "/assets/overlay-layout.css";
      document.head.appendChild(style);
      frame = document.createElement("div");
      frame.id = "vc-layout-frame";
      frame.setAttribute("aria-hidden", "true");
      frame.append(document.createElement("b"), document.createElement("small"));
      document.body.appendChild(frame);
      global.addEventListener("resize", size);
    }
    frame.firstChild.textContent = String(title || "Overlay").replace(/^Void Compass\s+/i, "").toUpperCase();
    size();
  }

  function size() {
    if (frame) frame.lastChild.textContent = `${global.innerWidth} × ${global.innerHeight}`;
  }

  function hide() {
    if (!frame) return;
    global.removeEventListener("resize", size);
    frame.remove();
    document.getElementById("vc-layout-style")?.remove();
    frame = null;
  }

  global.VoidCompassLayout = Object.freeze({
    apply(health) {
      if (health && health.layout) show(health.title);
      else hide();
    },
  });
})(window);
