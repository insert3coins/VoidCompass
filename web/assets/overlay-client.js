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
  // The public name is retained for existing pages. Native overlays receive
  // atomic envelopes from the shared host; HTTP also bootstraps standalone
  // pages and remains available if the host's message channel is interrupted.
  function startPolling(options) {
    const overlay = String(options.overlay || "");
    const suffix = `token=${encodeURIComponent(options.token || "")}&overlay=${encodeURIComponent(overlay)}`;
    let generation = -1, layout = -1, appliedRevision = -1, appliedLayout = -1;
    let measurement = 0, ready = false, snapshot = null, current = null;
    let running = false, reporting = false, polling = false, stopped = false;
    let active = null, pendingState = null, ordered = [];
    let lastPush = -Infinity, shapeTimer = 0;

    async function request(path, body, extra = "") {
      const controller = new AbortController();
      const timeout = global.setTimeout(() => controller.abort(), 4000);
      try {
        const response = await fetch(`${path}?${suffix}${extra}`, body === undefined
          ? {cache: "no-store", signal: controller.signal}
          : {method: "POST", headers: {"Content-Type": "application/json"},
            body: JSON.stringify(body), signal: controller.signal});
        // Consume every response, including errors, to release native buffers.
        const result = await response.json().catch(() => null);
        if (!response.ok) throw new Error(`Overlay HTTP ${response.status}`);
        return result;
      } finally {
        global.clearTimeout(timeout);
      }
    }

    async function announceReady(epoch) {
      if (stopped || ready || epoch !== generation || appliedRevision < 0) return;
      const reply = await request("/api/ready", {generation: epoch, renderer: rendererName()});
      if (epoch === generation) ready = reply?.ready === true;
    }

    async function report(record) {
      if (stopped || !record || record.generation !== generation) return;
      let height = typeof options.contentHeight === "function" ? Number(options.contentHeight())
        : Number(options.contentHeight || 0);
      if (!Number.isFinite(height) || height < 0) height = 0;
      const body = {generation: record.generation, layout_revision: record.layout_revision,
        revision: record.revision, measurement: ++measurement, measured: true,
        content_height: Math.ceil(height), shapes: windowShapes()};
      const reply = await request("/api/rendered", body);
      if (reply?.accepted && record.generation === generation) await announceReady(record.generation);
    }

    async function reportCurrent() {
      if (stopped || running || reporting || !current) return;
      reporting = true;
      try { await report(current); }
      catch (error) { options.onError?.(error); }
      finally { reporting = false; }
    }

    function remeasure() {
      global.clearTimeout(shapeTimer);
      const epoch = generation;
      shapeTimer = global.setTimeout(async () => {
        const animations = (document.getAnimations?.() || []).filter((animation) =>
          animation.playState === "running" && Number.isFinite(animation.effect?.getComputedTiming?.().endTime));
        if (animations.length) {
          await Promise.race([Promise.allSettled(animations.map((animation) => animation.finished)),
            new Promise((resolve) => global.setTimeout(resolve, 1500))]);
        }
        if (epoch === generation && !stopped) reportCurrent();
      }, 120);
    }

    async function pump() {
      if (running || stopped) return;
      running = true;
      let failed = false;
      try {
        while (!stopped && (ordered.length || pendingState)) {
          const record = ordered.length ? ordered.shift() : pendingState;
          if (record === pendingState) pendingState = null;
          if (record.generation !== generation || record.revision < appliedRevision) continue;
          active = record;
          // Intermediate ordinary states are replaceable. Every retained
          // notification/companion event is passed through render in order.
          if (pendingState && pendingState.revision <= record.revision) pendingState = null;
          snapshot = record.snapshot;
          if (!record.applied) {
            await options.render(snapshot);
            record.applied = true;
          }
          if (record.generation !== generation) continue;
          appliedRevision = record.revision;
          appliedLayout = record.layout_revision;
          current = record;
          // DOM measurement forces layout without waiting for an animation
          // frame, which a hidden WebView may never run.
          await report(record);
          remeasure();
        }
      } catch (error) {
        failed = true;
        if (active?.generation === generation) {
          if (active.ordered) ordered.unshift(active);
          else if (!pendingState || active.revision > pendingState.revision) pendingState = active;
        }
        options.onError?.(error);
      } finally {
        active = null;
        running = false;
        if (!failed && !stopped && (ordered.length || pendingState)) pump();
      }
    }

    function receive(packet, pushed = false) {
      if (stopped || packet?.type !== "voidcompass.overlay" || packet.overlay !== overlay) return;
      const epoch = Number(packet.generation), nextLayout = Number(packet.layout_revision);
      if (!Number.isInteger(epoch) || !Number.isInteger(nextLayout) || epoch < generation
          || (epoch === generation && nextLayout < layout)) return;
      if (pushed) lastPush = Date.now();
      if (epoch !== generation) {
        generation = epoch; layout = -1; appliedRevision = -1; appliedLayout = -1;
        measurement = 0; ready = false; ordered = []; pendingState = null; current = null;
      }
      layout = nextLayout;
      global.VoidCompassFrameCap?.set(packet.health?.frame_rate);
      global.VoidCompassLayout?.apply(packet.health || {});
      options.onContact?.();
      for (const item of packet.deliveries || []) {
        const revision = Number(item.revision);
        if (!Number.isInteger(revision) || revision < appliedRevision
            || (revision === appliedRevision && nextLayout <= appliedLayout)) continue;
        const record = {...item, revision, generation: epoch, layout_revision: nextLayout};
        if (item.ordered && revision > appliedRevision) {
          if (active?.generation === epoch && active.revision === revision) {
            if (nextLayout > active.layout_revision) pendingState = {...record, ordered: false};
            continue;
          }
          const queued = ordered.find((queued) => queued.revision === revision);
          if (!queued) ordered.push(record);
          else if (nextLayout > queued.layout_revision) queued.layout_revision = nextLayout;
        } else if (!pendingState || revision >= pendingState.revision) {
          pendingState = record;
        }
      }
      ordered.sort((first, second) => first.revision - second.revision);
      if (ordered.length || pendingState) pump();
      else reportCurrent(); // real browser heartbeat, including hidden pages
    }

    async function poll(force = false) {
      if (stopped || polling || (!force && Date.now() - lastPush < 3000)) return;
      polling = true;
      try {
        // Data and revision are read under the same server lock.
        const packet = await request("/api/snapshot", undefined, "&envelope=1");
        receive(packet);
      } catch (error) { options.onError?.(error); }
      finally { polling = false; }
    }

    const nativeMessage = (event) => receive(event.data, true);
    const directMessage = (packet) => receive(packet, true);
    global.chrome?.webview?.addEventListener("message", nativeMessage);
    global.__voidcompassDeliver = directMessage;
    global.__voidcompassPoll = () => poll(true);
    global.addEventListener("resize", remeasure);
    document.fonts?.ready.then(() => { if (!stopped) remeasure(); });
    poll();
    const timer = global.setInterval(poll, Math.max(100, Number(options.interval) || 200));
    function stop() {
      stopped = true;
      ordered = []; pendingState = null;
      global.clearInterval(timer); global.clearTimeout(shapeTimer);
      global.removeEventListener("resize", remeasure);
      global.chrome?.webview?.removeEventListener("message", nativeMessage);
      if (global.__voidcompassDeliver === directMessage) delete global.__voidcompassDeliver;
    }
    global.addEventListener("pagehide", stop, {once: true});
    return {poll: () => poll(true), refresh: () => poll(true),
      rerender: () => { if (snapshot) { options.render(snapshot); remeasure(); } }, stop};
  }


  // Fit a page to the window it really got (5.5.3.9). The app sizes an
  // overlay window as its design size x the text size x the monitor's
  // scaling; if Windows draws the page at another scale (a scaling setting
  // the app can't see, the window sized against another monitor), the page
  // lays out wider than its window, its words are cut short, and the height
  // it reports makes the window too short for its last rows. So: when the
  // window is narrower than the design width at this text size, the page
  // zooms itself down to fit it, and reports its height in the app's units.
  function fitToWindow(root, designWidth, effects = {}) {
    if (!root) return 1;
    const wanted = Number(designWidth) * clamp(effects.text_scale, .75, 2, 1);
    const ratio = global.innerWidth > 0 && wanted > 0 ? global.innerWidth / wanted : 1;
    const fit = ratio < .985 ? Math.max(.4, ratio) : 1;
    root.style.zoom = fit === 1 ? "" : fit.toFixed(4);
    root.dataset.fit = String(fit);
    root.dataset.fitWidth = String(designWidth);
    return fit;
  }

  // The page's height for the app: as tall as it would be at its design
  // width (what the window is sized from), at least ``minimum``.
  function designHeight(root, minimum = 0) {
    if (!root) return minimum;
    const fit = Number(root.dataset.fit) || 1;
    return Math.max(minimum, Math.ceil(root.getBoundingClientRect().height / fit + 2));
  }

  // The window being resized refits the pages that asked to be fitted.
  global.addEventListener("resize", () => {
    for (const root of global.document.querySelectorAll("[data-fit-width]")) {
      const scale = Number(global.getComputedStyle(root).getPropertyValue("--scale")) || 1;
      fitToWindow(root, Number(root.dataset.fitWidth), {text_scale: scale});
    }
  });

  global.VoidCompassOverlay = Object.freeze({applyTheme, startPolling, fitToWindow, designHeight});
})(window);
