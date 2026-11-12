/** The Dashboard as the whole ship (5.7.8): the panels for what you're doing
 * lead, each appearing only when there's something in it, and the small
 * things worth seeing. The panels draw the Navigation HUD's own page blocks,
 * so the HUD in the cockpit and the deck agree. */

const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (ch) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[ch]));
let lastHtml = "";
const panelMarkup = new WeakMap();
function block(b) {
  if (b.type === "hero") return `<div class="br-hero br-${esc(b.tone)}"><small>${esc(b.title)}</small><b>${esc(b.value)}</b>${b.sub ? `<span>${esc(b.sub)}</span>` : ""}</div>`;
  if (b.type === "stats") return `<div class="br-stats">${(b.items || []).map((item) => `<div><small>${esc(item.label)}</small><b class="br-${esc(item.tone)}">${esc(item.value)}</b></div>`).join("")}</div>`;
  if (b.type === "bars") return `<div class="br-bars">${(b.items || []).map((item) => `<div><span>${esc(item.label)}</span><i><em class="br-${esc(item.tone)}" style="width:${Math.round((item.ratio || 0) * 100)}%"></em></i><b>${esc(item.value)}</b></div>`).join("")}</div>`;
  if (b.type === "list") return `<div class="br-list">${b.title ? `<small>${esc(b.title)}</small>` : ""}${(b.items || []).map((item) => `<div><span class="br-${esc(item.tone)}">${esc(item.name)}</span><em>${esc(item.detail)}</em><b>${esc(item.value)}</b></div>`).join("")}${b.more ? `<em>+${b.more} more</em>` : ""}</div>`;
  if (b.type === "note") return `<p class="br-note br-${esc(b.tone)}">${esc(b.text)}</p>`;
  return "";
}

function panel(p) {
  if (p.id === "crew") {
    return `<article class="card br-card" data-br-panel="crew"><header><span>THE CREW</span><b>ON WATCH</b></header><div class="br-crew-name">${esc(p.name)}</div>
      ${p.thought ? `<blockquote class="br-thought">“${esc(p.thought)}”</blockquote>` : ""}${p.rota ? `<p class="br-note">${esc(p.rota)}</p>` : ""}
      <div class="br-actions"><button type="button" data-page="watcher">COMPANION ›</button></div></article>`;
  }
  if (p.id === "orders") {
    return `<article class="card br-card" data-br-panel="orders"><header><span>CREW ORDERS</span><b>${p.items.length}</b></header>
      ${p.items.map((item) => `<div class="br-order"><small>${esc(item.tag)} · ${esc(item.officer_name || item.officer)}</small><b>${esc(item.title)}</b>
        ${item.step ? `<span>${esc(item.step)}</span>` : ""}${item.distance ? `<em>${esc(item.distance)}</em>` : ""}
        ${item.progress !== null && item.progress !== undefined ? `<i class="br-progress"><em style="width:${Math.round((item.progress || 0) * 100)}%"></em></i>` : ""}
        ${item.plot && item.id ? `<button type="button" data-br-plot="${esc(item.id)}" title="Copy the order's target system">COPY SYSTEM</button>` : ""}</div>`).join("")}
      <div class="br-actions"><button type="button" data-page="watcher">ORDERS ›</button></div></article>`;
  }
  const link = {mining: ["mining", "MINING COMMAND"], trade: ["trading", "TRADING"], colony: ["colonisation", "COLONISATION"], carrier: ["carrier", "CARRIER COMMAND"], powerplay: ["powerplay", "POWERPLAY"], station: ["trading", "STATION MARKET"], expedition: ["mission", "EXPEDITION"]}[p.id];
  return `<article class="card br-card" data-br-panel="${esc(p.id)}"><header><span>${esc(p.label)}</span><b>${esc(p.title)}</b></header>
    ${(p.blocks || []).map(block).join("")}${link ? `<div class="br-actions"><button type="button" data-page="${link[0]}">${link[1]} ›</button></div>` : ""}</article>`;
}

// Where the pad is (bgol's LandingPad layouts, as ED-Outrider draws them).
function padMap(map) {
  if (!map) return "";
  if (map.kind === "starport") {
    const dots = (map.pads || []).map(([sector, depth, place, count], index) => {
      const angle = (sector * 30 + (place - (count + 1) / 2) * 7) * Math.PI / 180;
      const r = 18 + depth * 11;
      const on = index + 1 === map.pad;
      return `<circle cx="${(50 + r * Math.sin(angle)).toFixed(1)}" cy="${(50 - r * Math.cos(angle)).toFixed(1)}" r="${on ? 4 : 2.2}" class="${on ? "br-pad-on" : "br-pad"}"/>`;
    }).join("");
    return `<svg class="br-padmap" viewBox="0 0 100 100" aria-hidden="true"><circle cx="50" cy="50" r="48" class="br-pad-ring"/><rect x="44" y="94" width="12" height="5" class="br-pad-slot"/>${dots}</svg>`;
  }
  const boxes = map.pads || [];
  const xs = boxes.flatMap(([x, , w]) => [x, x + w]);
  const minX = Math.min(-30, ...xs) - 2, maxX = Math.max(30, ...xs) + 2;
  const outline = (map.outline || []).map(([x, y]) => `${x},${y}`).join(" ");
  const rects = boxes.map(([x, y, w, h], index) => `<rect x="${x}" y="${y}" width="${w}" height="${h}" class="${index + 1 === map.pad ? "br-pad-on" : "br-pad"}"/>`).join("");
  return `<svg class="br-padmap" viewBox="${minX} -50 ${maxX - minX} 95" aria-hidden="true">${outline ? `<polygon points="${outline}" class="br-pad-ring"/>` : ""}${rects}</svg>`;
}

export function renderBridge(activity, ui) {
  const slot = document.getElementById("bridge-activity");
  if (slot && !slot.dataset.bound) {
    slot.dataset.bound = "1";
    slot.addEventListener("click", async (event) => {
      const plot = event.target.closest("[data-br-plot]");
      if (!plot) return;
      if (await ui?.command?.("workspace", {page: "orders", operation: "plot", id: plot.dataset.brPlot})) ui?.showToast?.("Target system copied");
    });
  }
  const label = document.getElementById("bridge-activity-label");
  if (label) label.textContent = activity?.label || "";
  if (slot) {
    // Only what's in use: no panels and nothing worth a look, no section.
    const small = (activity?.small || []).map((item) => `<div class="br-small br-small-${esc(item.kind)}"><small>${esc(item.label)}</small><span>${esc(item.text)}</span>${item.kind === "pad" ? padMap(item.map) : ""}</div>`).join("");
    const html = (activity?.panels || []).map(panel).join("")
      + (small ? `<article class="card br-card br-worth" data-br-panel="worth"><header><span>WORTH A LOOK</span></header><div class="bridge-small">${small}</div></article>` : "");
    if (html !== lastHtml) {
      lastHtml = html;
      const template = document.createElement("template");
      template.innerHTML = html;
      const existing = new Map([...slot.children].map((node) => [node.dataset.brPanel, node]));
      const ordered = [...template.content.children].map((node) => {
        const previous = existing.get(node.dataset.brPanel);
        const markup = node.outerHTML;
        if (previous && panelMarkup.get(previous) === markup) return previous;
        panelMarkup.set(node, markup);
        return node;
      });
      for (const node of [...slot.children]) if (!ordered.includes(node)) node.remove();
      ordered.forEach((node, index) => {
        if (slot.children[index] !== node) slot.insertBefore(node, slot.children[index] || null);
      });
      slot.hidden = !html;
    }
  }
}
