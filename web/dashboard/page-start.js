// Page-start witness and first aid. Some launches lose a burst of this page's
// files in its first second: stylesheets (a half-styled deck) or app.js (a
// frozen boot screen). This classic script runs before any module, fetches a
// lost stylesheet again, restarts a page whose client could not load, and
// tells the host log what the browser saw.
(() => {
  "use strict";
  const token = new URLSearchParams(location.search).get("token") || "";
  const started = performance.now();
  const seen = [];
  const styleRetries = new Map();
  const RELOAD_KEY = `voidcompass.page-start.reloaded.${token}`;
  let reported = false;
  let restarting = false;

  function post(message) {
    try {
      fetch(`/api/command?token=${encodeURIComponent(token)}`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({action: "client_error", source: "page-start", message: String(message).slice(0, 2000)}),
        keepalive: true,
      }).catch(() => {});
    } catch (_error) { /* Reporting must never break the page. */ }
  }

  function scriptTimings() {
    return performance.getEntriesByType("resource")
      .filter((entry) => /\.js$/.test(new URL(entry.name).pathname))
      .map((entry) => `${new URL(entry.name).pathname} ${entry.responseStatus || "?"} ${Math.round(entry.duration)}ms`)
      .join(", ");
  }

  // A lost stylesheet leaves every panel it styles in a mess; fetch it again.
  function retryStylesheet(link) {
    const href = link.getAttribute("href") || "";
    const attempt = (styleRetries.get(href) || 0) + 1;
    if (attempt > 3) return false;
    styleRetries.set(href, attempt);
    window.setTimeout(() => {
      const again = link.cloneNode();
      again.href = `${href}${href.includes("?") ? "&" : "?"}retry=${attempt}`;
      again.addEventListener("load", () => link.remove(), {once: true});
      link.after(again);
    }, 150 * attempt);
    return true;
  }

  // Without app.js nothing can start; one immediate reload beats waiting for
  // the host's rescue. The session flag keeps a genuinely broken build from
  // reloading forever.
  function restartOnce() {
    try {
      if (sessionStorage.getItem(RELOAD_KEY)) return false;
      sessionStorage.setItem(RELOAD_KEY, "1");
    } catch (_error) {
      return false;
    }
    restarting = true;
    window.setTimeout(() => location.reload(), 250);
    return true;
  }

  window.addEventListener("error", (event) => {
    const target = event.target;
    const resource = target && target !== window ? (target.src || target.href || "") : "";
    const path = resource ? new URL(resource, location.href).pathname : "";
    const message = resource ? `failed to load ${path}` : String(event.error?.stack || event.message || "script error");
    seen.push(message);
    let action = "";
    if (target instanceof HTMLLinkElement && target.rel === "stylesheet" && retryStylesheet(target)) {
      action = " · fetching again";
    } else if (target instanceof HTMLScriptElement && path.endsWith("/app.js")
        && !window.__voidcompassDeckStarted && restartOnce()) {
      action = " · reloading the page";
    }
    if (!window.__voidcompassDeckStarted || action) post(`before client start: ${message}${action}`);
  }, true);

  window.addEventListener("unhandledrejection", (event) => {
    if (window.__voidcompassDeckStarted) return;
    const message = String(event.reason?.stack || event.reason || "rejection");
    seen.push(message);
    post(`before client start: ${message}`);
  });

  // Module scripts run before DOMContentLoaded, so by then app.js has either
  // started its client or failed.
  function check(stage) {
    // A page about to reload itself has already said why.
    if (reported || restarting) return;
    if (window.__voidcompassDeckStarted) {
      try { sessionStorage.removeItem(RELOAD_KEY); } catch (_error) { /* Optional. */ }
      return;
    }
    reported = true;
    post(`client not started at ${stage} (${Math.round(performance.now() - started)} ms, `
      + `${document.readyState}): ${seen.join(" | ") || "no error seen"} · scripts: ${scriptTimings() || "none"}`);
  }
  document.addEventListener("DOMContentLoaded", () => window.setTimeout(() => check("DOMContentLoaded"), 0));
  window.addEventListener("load", () => window.setTimeout(() => check("load"), 250));
})();
