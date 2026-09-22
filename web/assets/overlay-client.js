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
    document.body.style.opacity = String(clamp(effects.opacity, .4, 1, 1));
    if (root) {
      root.classList.toggle("no-crt", !effects.crt);
      root.classList.toggle("reduced-motion", Boolean(effects.reduced_motion));
    }
    return resolved;
  }

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
          method: "POST", body: "{}",
        });
        ready = response.ok;
      } catch (_) { /* A later health poll retries the handshake. */ }
    }

    async function refresh(nextRevision) {
      const response = await fetch(`/api/snapshot?${suffix}`, {cache: "no-store"});
      if (!response.ok) return;
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
      try {
        const response = await fetch(`/api/rendered?${suffix}`, {
          method: "POST", headers: {"Content-Type": "application/json"},
          body: JSON.stringify(rendered),
        });
        if (response.ok) {
          revision = nextRevision;
          renderedRevision = nextRevision;
          await announceReady();
        }
      } catch (_) { /* A later poll retries the renderer handshake. */ }
    }

    async function poll() {
      if (polling) return;
      polling = true;
      try {
        const response = await fetch(`/api/health?${suffix}`, {cache: "no-store"});
        if (response.ok) {
          const nextRevision = Number((await response.json()).revision);
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
    const timer = global.setInterval(poll, Math.max(100, Number(options.interval) || 200));
    return {poll, refresh, rerender, stop: () => global.clearInterval(timer)};
  }

  global.VoidCompassOverlay = Object.freeze({applyTheme, startPolling});
})(window);
