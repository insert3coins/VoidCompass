/* Layered stellar backdrop inspired by our neon-matrix Twitch scene.
   Local Canvas2D only: no network assets, WebGL or startup dependencies. */
(() => {
  'use strict';
  const canvas = document.getElementById('boot-starfield');
  const boot = document.getElementById('boot');
  const ctx = canvas?.getContext('2d');
  if (!ctx || !boot) return;
  const motion = matchMedia('(prefers-reduced-motion: reduce)');
  let frame = 0, last = 0, elapsed = 0, width = 0, height = 0;
  let accent = '#00d1ff', warm = '#ff7a18';
  let seed = 1291;
  const random = () => {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
    return seed / 4294967296;
  };
  // Stable coordinates avoid flicker or reshuffling during resize/theme changes.
  const stars = Array.from({length: 760}, (_, index) => {
    const x = random();
    const band = index < 220;
    return {x, y: band ? .30 + x * .30 + (random() + random() + random() - 1.5) * .15 : random(),
      depth: random(), radius: .35 + random() ** 3 * 1.35,
      alpha: .25 + random() * .65, phase: random() * Math.PI * 2,
      tint: random()};
  });
  const reduced = () => motion.matches || document.body.classList.contains('reduced-motion');
  const visible = () => !document.hidden && !boot.hidden
    && !document.body.classList.contains('ready');

  function draw() {
    ctx.clearRect(0, 0, width, height);
    const t = elapsed / 1000;
    for (const star of stars) {
      const drift = reduced() ? 0 : t * (.7 + star.depth * 2.2);
      const x = ((star.x * width + drift) % (width + 8)) - 4;
      const y = star.y * height + (reduced() ? 0 : Math.sin(t * .07 + star.phase) * (1 + star.depth * 3));
      const shimmer = reduced() ? 1 : .88 + Math.sin(t * (.3 + star.depth * .3) + star.phase) * .12;
      ctx.globalAlpha = star.alpha * shimmer;
      ctx.fillStyle = star.tint < .08 ? accent : star.tint < .12 ? warm : '#d9ecff';
      ctx.beginPath();
      ctx.arc(x, y, star.radius, 0, Math.PI * 2);
      ctx.fill();
      if (star.radius > 1.35) {
        ctx.globalAlpha *= .13;
        ctx.beginPath();
        ctx.arc(x, y, star.radius * 3.4, 0, Math.PI * 2);
        ctx.fill();
      }
    }
    ctx.globalAlpha = 1;
  }

  function tick(now) {
    frame = 0;
    if (!visible() || reduced()) { last = 0; return; }
    if (!last || now - last >= 1000 / 30) {
      elapsed += last ? Math.min(now - last, 100) : 0;
      last = now;
      draw();
    }
    frame = requestAnimationFrame(tick);
  }

  function refresh() {
    cancelAnimationFrame(frame);
    frame = 0;
    last = 0;
    if (!visible()) return;
    const box = boot.getBoundingClientRect();
    width = Math.max(1, box.width);
    height = Math.max(1, box.height);
    const ratio = Math.min(devicePixelRatio || 1, 1.5);
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    const palette = getComputedStyle(document.documentElement);
    accent = palette.getPropertyValue('--accent').trim() || '#00d1ff';
    warm = palette.getPropertyValue('--orange').trim() || '#ff7a18';
    draw();
    if (!reduced()) frame = requestAnimationFrame(tick);
  }
  const resize = new ResizeObserver(refresh);
  resize.observe(boot);
  const changes = new MutationObserver(refresh);
  changes.observe(boot, {attributes: true, attributeFilter: ['hidden', 'class']});
  changes.observe(document.body, {attributes: true, attributeFilter: ['class']});
  changes.observe(document.documentElement, {attributes: true, attributeFilter: ['style', 'class']});
  motion.addEventListener('change', refresh);
  document.addEventListener('visibilitychange', refresh);
  window.addEventListener('pagehide', () => {
    cancelAnimationFrame(frame);
    resize.disconnect();
    changes.disconnect();
    motion.removeEventListener('change', refresh);
    document.removeEventListener('visibilitychange', refresh);
  }, {once: true});
  refresh();
})();
