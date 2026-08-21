(() => {
  "use strict";
  const params = new URLSearchParams(location.search);
  const token = params.get("token") || "";
  const overlay = params.get("overlay") || "";
  const suffix = `token=${encodeURIComponent(token)}&overlay=${encodeURIComponent(overlay)}`;
  const canvas = document.getElementById("overlay");
  const ctx = canvas.getContext("2d", { alpha: true, desynchronized: true });
  let readySent = false;
  let lastRevision = -1;
  let revisionPollActive = false;

  function dash(value) {
    if (!value) return [];
    return String(value).split(/[ ,]+/).map(Number).filter(Number.isFinite);
  }

  function strokeFill(item) {
    ctx.lineWidth = Math.max(0.1, Number(item.width || 1));
    ctx.strokeStyle = item.outline || item.fill || "transparent";
    ctx.fillStyle = item.fill || "transparent";
    ctx.setLineDash(dash(item.dash));
    ctx.lineCap = item.capstyle === "projecting" ? "square" : (item.capstyle || "butt");
    ctx.lineJoin = item.joinstyle || "miter";
  }

  function path(coords, close) {
    if (coords.length < 2) return;
    ctx.beginPath();
    ctx.moveTo(coords[0], coords[1]);
    for (let i = 2; i + 1 < coords.length; i += 2) ctx.lineTo(coords[i], coords[i + 1]);
    if (close) ctx.closePath();
  }

  function paintPath(item, close) {
    const coords = item.coords || [];
    strokeFill(item);
    path(coords, close);
    if (item.fill && item.type !== "line") ctx.fill();
    if (item.outline || item.type === "line") ctx.stroke();
  }

  function textPosition(anchor) {
    const value = String(anchor || "center").toLowerCase();
    return {
      align: value.includes("w") ? "left" : value.includes("e") ? "right" : "center",
      baseline: value.includes("n") ? "top" : value.includes("s") ? "bottom" : "middle",
    };
  }

  function drawText(item) {
    const font = item.font || {};
    const style = font.slant === "italic" ? "italic" : "normal";
    const weight = font.weight === "bold" ? "700" : "400";
    const size = Math.max(1, Number(font.size || 9));
    const family = JSON.stringify(font.family || "Courier New");
    const position = textPosition(item.anchor);
    const coords = item.coords || [0, 0];
    const lines = String(item.text || "").split("\n");
    const lineHeight = size * 1.22;
    let y = Number(coords[1] || 0);
    if (position.baseline === "middle" && lines.length > 1) y -= (lines.length - 1) * lineHeight / 2;
    if (position.baseline === "bottom" && lines.length > 1) y -= (lines.length - 1) * lineHeight;
    ctx.save();
    ctx.translate(Number(coords[0] || 0), Number(coords[1] || 0));
    ctx.rotate(Number(item.angle || 0) * Math.PI / 180);
    ctx.translate(-Number(coords[0] || 0), -Number(coords[1] || 0));
    ctx.font = `${style} ${weight} ${size}px ${family}`;
    ctx.textAlign = position.align;
    ctx.textBaseline = position.baseline;
    ctx.fillStyle = item.fill || "#ffffff";
    for (let i = 0; i < lines.length; i += 1) ctx.fillText(lines[i], Number(coords[0] || 0), y + i * lineHeight);
    ctx.restore();
  }

  function draw(item) {
    const c = item.coords || [];
    switch (item.type) {
      case "line":
        paintPath(item, false);
        break;
      case "polygon":
        paintPath(item, true);
        break;
      case "rectangle":
      case "oval": {
        if (c.length < 4) break;
        strokeFill(item);
        const x = Math.min(c[0], c[2]);
        const y = Math.min(c[1], c[3]);
        const w = Math.abs(c[2] - c[0]);
        const h = Math.abs(c[3] - c[1]);
        ctx.beginPath();
        if (item.type === "oval") ctx.ellipse(x + w / 2, y + h / 2, w / 2, h / 2, 0, 0, Math.PI * 2);
        else ctx.rect(x, y, w, h);
        if (item.fill) ctx.fill();
        if (item.outline) ctx.stroke();
        break;
      }
      case "arc": {
        if (c.length < 4) break;
        strokeFill(item);
        const x = Math.min(c[0], c[2]);
        const y = Math.min(c[1], c[3]);
        const w = Math.abs(c[2] - c[0]);
        const h = Math.abs(c[3] - c[1]);
        const start = -Number(item.start || 0) * Math.PI / 180;
        const end = start - Number(item.extent || 90) * Math.PI / 180;
        ctx.save();
        ctx.translate(x + w / 2, y + h / 2);
        ctx.scale(w / 2, h / 2);
        ctx.beginPath();
        ctx.arc(0, 0, 1, start, end, true);
        ctx.restore();
        if (item.outline) ctx.stroke();
        break;
      }
      case "text":
        drawText(item);
        break;
    }
  }

  async function render(model) {
    const scene = model && model.scene ? model.scene : { width: 1, height: 1, items: [] };
    const width = Math.max(1, Number(scene.width || 1));
    const height = Math.max(1, Number(scene.height || 1));
    const ratio = Math.max(1, window.devicePixelRatio || 1);
    if (canvas.width !== Math.round(width * ratio) || canvas.height !== Math.round(height * ratio)) {
      canvas.width = Math.round(width * ratio);
      canvas.height = Math.round(height * ratio);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
    }
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, width, height);
    ctx.globalCompositeOperation = "source-over";
    for (const item of scene.items || []) draw(item);
    if (!readySent) {
      readySent = true;
      try { await fetch(`/api/ready?${suffix}`, { method: "POST", body: "{}" }); } catch (_) {}
    }
  }

  async function refresh(revision = null) {
    try {
      const response = await fetch(`/api/snapshot?${suffix}`, { cache: "no-store" });
      if (response.ok) {
        await render(await response.json());
        const value = Number(revision);
        if (Number.isFinite(value)) {
          lastRevision = value;
          try {
            await fetch(`/api/rendered?${suffix}`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ revision: value }),
            });
          } catch (_) {}
        }
      }
    } catch (_) {}
  }

  async function pollRevision() {
    if (revisionPollActive) return;
    revisionPollActive = true;
    try {
      const response = await fetch(`/api/health?${suffix}`, { cache: "no-store" });
      if (!response.ok) return;
      const health = await response.json();
      const revision = Number(health.revision);
      if (Number.isFinite(revision) && revision !== lastRevision) {
        await refresh(revision);
      }
    } catch (_) {
    } finally {
      revisionPollActive = false;
    }
  }

  pollRevision();
  // Avoid one permanent HTTP connection per WebView. A health check is tiny,
  // and the full scene is requested only after its revision changes.
  window.setInterval(pollRevision, 400);
})();
