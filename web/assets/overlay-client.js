(function (global) {
  "use strict";

  const THEME_MAPPING = {
    bg: "bg", panel: "panel", panel_alt: "alt", panel_raised: "raised",
    header: "header", input: "input", inset: "inset", border: "border",
    border_soft: "soft", selection: "selection", accent: "accent",
    orange: "orange", text: "text", muted: "muted", dim: "dim",
    green: "green", yellow: "yellow", red: "red",
  };

  function clamp(value, low, high, fallback) {
    const number = Number(value);
    return Number.isFinite(number) ? Math.max(low, Math.min(high, number)) : fallback;
  }

  function applyTheme(root, palette = {}, effects = {}, options = {}) {
    const mapping = options.mapping || THEME_MAPPING;
    const resolved = {};
    for (const [key, css] of Object.entries(mapping)) {
      const value = String(palette[key] || "");
      if (/^#[0-9a-f]{6}$/i.test(value)) {
        document.documentElement.style.setProperty(`--${css}`, value);
      }
      resolved[css] = value || getComputedStyle(document.documentElement)
        .getPropertyValue(`--${css}`).trim();
    }
    document.documentElement.style.setProperty(
      "--scale",
      String(clamp(effects.text_scale, options.scaleMin ?? .75, options.scaleMax ?? 2, 1)),
    );
    // Overlay Studio's OPACITY fades the whole window in the host (Windows'
    // layered-window alpha); fading the page as well would apply it twice.
    document.body.style.removeProperty("opacity");
    if (root) {
      root.classList.toggle("no-crt", !effects.crt);
      root.classList.toggle("reduced-motion", Boolean(effects.reduced_motion));
    }
    return resolved;
  }

  // --- The page's visible shapes (5.5.3.3.1) -----------------------------------
  // Where WebView2 draws without the GPU, its transparent pixels come out
  // black: a dark box round anything not rectangular. With the Dark box fix
  // the host cuts the window to these shapes. They are the elements marked
  // data-window-shape ("circle", or anything else for its box), or else the
  // page's <main>; each box keeps its rounded corners or clip-path polygon.
  // Device pixels, polygons of whole points.
  function length(token, size) {
    const text = String(token || "").trim();
    if (text.startsWith("calc(")) {
      let total = 0;
      for (const [, sign, term] of text.slice(5, -1).matchAll(/([+-]?)\s*([\d.]+(?:px|%)?)/g)) {
        total += (sign === "-" ? -1 : 1) * length(term, size);
      }
      return total;
    }
    const number = parseFloat(text);
    if (!Number.isFinite(number)) return 0;
    return text.endsWith("%") ? number / 100 * size : number;
  }

  function splitTop(text, separator) {
    const parts = [];
    let depth = 0, start = 0;
    for (let index = 0; index < text.length; index += 1) {
      const ch = text[index];
      if (ch === "(") depth += 1;
      else if (ch === ")") depth -= 1;
      else if (depth === 0 && (separator === " " ? /\s/.test(ch) : ch === separator)) {
        if (index > start) parts.push(text.slice(start, index));
        start = index + 1;
      }
    }
    if (start < text.length) parts.push(text.slice(start));
    return parts.map((part) => part.trim()).filter(Boolean);
  }

  function boxShape(node, box) {
    const style = getComputedStyle(node);
    const clip = String(style.clipPath || "");
    if (node.dataset.windowShape === "circle") {
      return Array.from({length: 40}, (_, step) => {
        const angle = step / 40 * Math.PI * 2;
        return [box.left + box.width / 2 + Math.cos(angle) * (box.width / 2 + .5),
          box.top + box.height / 2 + Math.sin(angle) * (box.height / 2 + .5)];
      });
    }
    if (clip.startsWith("polygon(")) {
      const points = splitTop(clip.slice(8, -1), ",").map((pair) => {
        const [x, y] = splitTop(pair, " ");
        return [box.left + length(x, box.width), box.top + length(y, box.height)];
      });
      if (points.length >= 3) return points;
    }
    const radius = (corner) => Math.min(length(String(style[corner] || "0").split(" ")[0], box.width), box.width / 2, box.height / 2);
    const corners = [
      [box.left, box.top, radius("borderTopLeftRadius"), Math.PI],
      [box.right, box.top, radius("borderTopRightRadius"), Math.PI * 1.5],
      [box.right, box.bottom, radius("borderBottomRightRadius"), 0],
      [box.left, box.bottom, radius("borderBottomLeftRadius"), Math.PI * .5],
    ];
    const points = [];
    for (const [x, y, r, start] of corners) {
      if (r < 1) { points.push([x, y]); continue; }
      const cx = x === box.left ? x + r : x - r;
      const cy = y === box.top ? y + r : y - r;
      const steps = Math.max(3, Math.min(16, Math.ceil(r / 5)));
      for (let step = 0; step <= steps; step += 1) {
        const angle = start + step / steps * Math.PI / 2;
        points.push([cx + Math.cos(angle) * r, cy + Math.sin(angle) * r]);
      }
    }
    return points;
  }

  function windowShapes() {
    let nodes = [...document.querySelectorAll("[data-window-shape]")];
    if (!nodes.length) nodes = [document.querySelector("main")].filter(Boolean);
    const ratio = global.devicePixelRatio || 1;
    const shapes = [];
    for (const node of nodes) {
      if (node.hidden || node.closest("[hidden]")) continue;
      const style = getComputedStyle(node);
      if (style.display === "none" || style.visibility === "hidden") continue;
      const box = node.getBoundingClientRect();
      if (box.width < 2 || box.height < 2) continue;
      shapes.push(boxShape(node, box).map(([x, y]) => [Math.round(x * ratio), Math.round(y * ratio)]));
      if (shapes.length >= 32) break;
    }
    return shapes;
  }

  // Which renderer the page has (for the logs): the GPU's name, or
  // SwiftShader when WebView2 draws in software.
  function rendererName() {
    try {
      const gl = document.createElement("canvas").getContext("webgl");
      if (!gl) return "no WebGL (software)";
      const info = gl.getExtension("WEBGL_debug_renderer_info");
      return String(info ? gl.getParameter(info.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER));
    } catch (_) {
      return "unknown";
    }
  }

  // Every reply is read to its end: an unread one keeps native buffers until
  // the garbage collector happens by, and overlays acknowledge many times an
  // hour (a leak that slowly grew the command deck's renderer the same way).
  const drain = (response) => response.arrayBuffer().catch(() => null);

  function startPolling(options) {
    const token = String(options.token || "");
    const overlay = String(options.overlay || "");
    const suffix = `token=${encodeURIComponent(token)}&overlay=${encodeURIComponent(overlay)}`;
    let revision = -1;
    let renderedRevision = -1;
    let polling = false;
    let ready = false;
    let snapshot = null;

    async function announceReady() {
      if (ready || renderedRevision < 0) return;
      try {
        const response = await fetch(`/api/ready?${suffix}`, {
          method: "POST", body: JSON.stringify({renderer: rendererName()}),
        });
        await drain(response);
        ready = response.ok;
      } catch (_) { /* A later health poll retries the handshake. */ }
    }

    async function refresh(nextRevision) {
      const response = await fetch(`/api/snapshot?${suffix}`, {cache: "no-store"});
      if (!response.ok) return void drain(response);
      snapshot = await response.json();
      options.render(snapshot);
      // Hidden WebViews may suspend animation frames. A page must still be
      // able to acknowledge its rendered DOM before the host will reveal it.
      await new Promise((resolve) => {
        let frame = 0;
        const finish = () => {
          global.clearTimeout(timer);
          global.cancelAnimationFrame(frame);
          resolve();
        };
        const timer = global.setTimeout(finish, 100);
        frame = global.requestAnimationFrame(finish);
      });
      const rendered = {revision: nextRevision};
      const height = typeof options.contentHeight === "function"
        ? Number(options.contentHeight())
        : Number(options.contentHeight);
      if (Number.isFinite(height) && height > 0) rendered.content_height = Math.ceil(height);
      rendered.shapes = windowShapes();
      lastShapes = JSON.stringify(rendered.shapes);
      try {
        const response = await fetch(`/api/rendered?${suffix}`, {
          method: "POST", headers: {"Content-Type": "application/json"},
          body: JSON.stringify(rendered),
        });
        await drain(response);
        if (response.ok) {
          revision = nextRevision;
          renderedRevision = nextRevision;
          await announceReady();
        }
      } catch (_) { /* A later poll retries the renderer handshake. */ }
      recheckShapes(nextRevision);
    }

    // Shapes measured mid-animation (a card sliding in) are measured again
    // once the animations settle, and sent if they moved.
    let lastShapes = "";
    let shapeTimer = 0;
    function recheckShapes(forRevision) {
      global.clearTimeout(shapeTimer);
      shapeTimer = global.setTimeout(async () => {
        const settling = (document.getAnimations?.() || []).filter((animation) =>
          animation.playState === "running" && Number.isFinite(animation.effect?.getComputedTiming?.().endTime));
        if (settling.length) {
          await Promise.race([Promise.allSettled(settling.map((animation) => animation.finished)),
            new Promise((resolve) => global.setTimeout(resolve, 1500))]);
        }
        const shapes = windowShapes();
        const key = JSON.stringify(shapes);
        if (key === lastShapes || forRevision !== renderedRevision) return;
        lastShapes = key;
        try {
          await drain(await fetch(`/api/rendered?${suffix}`, {
            method: "POST", headers: {"Content-Type": "application/json"},
            body: JSON.stringify({revision: forRevision, shapes}),
          }));
        } catch (_) { /* The next render reports them again. */ }
      }, 120);
    }
    global.addEventListener("resize", () => recheckShapes(renderedRevision));

    async function poll() {
      if (polling) return;
      polling = true;
      try {
        const response = await fetch(`/api/health?${suffix}`, {cache: "no-store"});
        if (!response.ok) await drain(response);
        if (response.ok) {
          const health = await response.json();
          global.VoidCompassFrameCap?.set(health.frame_rate);
          global.VoidCompassLayout?.apply(health);
          const nextRevision = Number(health.revision);
          if (Number.isFinite(nextRevision) && nextRevision !== revision) {
            await refresh(nextRevision);
          } else {
            await announceReady();
          }
        }
      } catch (_) { /* Overlay server startup/recovery is transient. */ }
      finally { polling = false; }
    }

    function rerender() {
      if (snapshot) options.render(snapshot);
    }

    poll();
    // The host calls this to fetch new data at once while the overlay is
    // hidden: a hidden WebView2's timers are throttled (down to about once a
    // minute), which left a newly shown overlay drawing old data (5.5.2.7).
    global.__voidcompassPoll = poll;
    const timer = global.setInterval(poll, Math.max(100, Number(options.interval) || 200));
    return {poll, refresh, rerender, stop: () => global.clearInterval(timer)};
  }

  global.VoidCompassOverlay = Object.freeze({applyTheme, startPolling});
})(window);
