(() => {
  "use strict";
  const params = new URLSearchParams(location.search);
  const token = params.get("token") || "";
  const overlay = params.get("overlay") || "heartbeat";
  const suffix = `token=${encodeURIComponent(token)}&overlay=${encodeURIComponent(overlay)}`;
  const root = document.getElementById("heartbeat");
  let revision = -1, polling = false, ready = false, pulseId = -1;

  function applyTheme(theme = {}, effects = {}) {
    for (const [key, css] of Object.entries({accent:"accent",orange:"orange",green:"green",red:"red",bg:"bg",panel:"panel",border:"border",text:"text",muted:"muted"})) { const value = String(theme[key] || ""); if (/^#[0-9a-f]{6}$/i.test(value)) document.documentElement.style.setProperty(`--${css}`, value); }
    const scale = Number(effects.text_scale);
    document.documentElement.style.setProperty("--scale", String(Number.isFinite(scale) ? Math.max(.85, Math.min(1.25, scale)) : 1));
    const opacity = Number(effects.opacity); document.body.style.opacity = String(Number.isFinite(opacity) ? Math.max(.4, Math.min(1, opacity)) : 1);
    root.classList.toggle("reduced-motion", Boolean(effects.reduced_motion));
  }

  function render(snapshot = {}) {
    applyTheme(snapshot.theme || {}, snapshot.effects || {});
    const model = snapshot.heartbeat || {};
    const stalled = Boolean(model.stalled);
    root.classList.toggle("stalled", stalled);
    root.classList.toggle("journal", model.kind === "journal");
    root.classList.toggle("status", model.kind === "status");
    root.classList.toggle("state-change", Boolean(model.state_changed));
    root.setAttribute("aria-label", stalled ? "Telemetry heartbeat stalled" : "Telemetry heartbeat active");
    root.title = stalled ? "Telemetry heartbeat stalled" : "Telemetry heartbeat active";
    const nextPulse = Number(model.pulse_id);
    if (!stalled && Number.isFinite(nextPulse) && nextPulse !== pulseId) {
      pulseId = nextPulse;
      root.classList.remove("beat");
      void root.offsetWidth;
      root.classList.add("beat");
    }
  }

  async function refresh(nextRevision) { const response = await fetch(`/api/snapshot?${suffix}`, {cache:"no-store"}); if (!response.ok) return; render(await response.json()); await new Promise((resolve) => requestAnimationFrame(resolve)); revision = nextRevision; try { await fetch(`/api/rendered?${suffix}`, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({revision:nextRevision,content_height:54})}); if (!ready) { ready = true; await fetch(`/api/ready?${suffix}`, {method:"POST",body:"{}"}); } } catch (_) {} }
  async function poll() { if (polling) return; polling = true; try { const response = await fetch(`/api/health?${suffix}`, {cache:"no-store"}); if (response.ok) { const next = Number((await response.json()).revision); if (Number.isFinite(next) && next !== revision) await refresh(next); } } catch (_) {} finally { polling = false; } }
  poll(); window.setInterval(poll, 160);
})();
