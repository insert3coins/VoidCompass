(() => {
  "use strict";
  const params = new URLSearchParams(location.search);
  const token = params.get("token") || "";
  const overlay = params.get("overlay") || "rig-tracker";
  const byId = (id) => document.getElementById(id);
  const root = byId("rigs");
  const NS = "http://www.w3.org/2000/svg";
  const Draw = window.VoidCompassRhinoDraw;

  const number = (value, fallback = 0) => Number.isFinite(Number(value)) ? Number(value) : fallback;
  const distance = (metres) => {
    const m = number(metres);
    return m >= 1000 ? `${(m / 1000).toFixed(m >= 10000 ? 0 : 1)}km` : `${Math.round(m)}m`;
  };
  const age = (at) => {
    const minutes = Math.max(0, Math.floor((Date.now() / 1000 - number(at)) / 60));
    if (minutes < 60) return `${minutes}m`;
    const hours = Math.floor(minutes / 60);
    return hours < 48 ? `${hours}h${minutes % 60}m` : `${Math.floor(hours / 24)}d`;
  };
  const credits = (value) => {
    const v = number(value);
    return v >= 1e9 ? `${(v / 1e9).toFixed(2)}B` : v >= 1e6 ? `${(v / 1e6).toFixed(2)}M` : v >= 1e3 ? `${Math.round(v / 1e3)}K` : `${Math.round(v)}`;
  };
  const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[char]));
  const colourOf = (name, spent) => spent ? "var(--dim)" : `rgb(${Draw.commodityColour(name).join(",")})`;

  let sections = {};
  let drawn = {};

  // Which way to swing, at a glance.
  const turn = (bearing) => {
    if (sections.heading == null || bearing == null) return "";
    const offset = ((number(bearing) - number(sections.heading) + 540) % 360) - 180;
    return Math.abs(offset) < 6 ? "▲" : Math.abs(offset) > 150 ? "▼" : offset > 0 ? "▶" : "◀";
  };

  function node(tag, className = "", text = "") {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== "") element.textContent = String(text);
    return element;
  }

  function part(id, markup) {
    const element = byId(id);
    element.hidden = !markup;
    if (markup && drawn[id] !== markup) {
      element.innerHTML = markup;
      drawn[id] = markup;
    }
  }

  // A dial: a ring with a needle pointing the way the rig lies (up is
  // straight ahead), or a filled ring when you're at it.
  // How far a rig is towards ready, 0 to 1, once your rigs have taught how
  // long they take (rig.ready_s); null before then.
  const readiness = (rig) => rig.tracked && number(rig.ready_s) > 0
    ? Math.max(0, Math.min(1, (Date.now() / 1000 - number(rig.at)) / number(rig.ready_s))) : null;

  function dial(rig) {
    const svg = document.createElementNS(NS, "svg");
    svg.setAttribute("viewBox", "0 0 40 40");
    svg.setAttribute("aria-hidden", "true");
    const ring = document.createElementNS(NS, "circle");
    ring.setAttribute("cx", "20"); ring.setAttribute("cy", "20"); ring.setAttribute("r", "15");
    ring.setAttribute("class", "ring");
    svg.appendChild(ring);
    if (!rig.tracked) return svg;
    // The countdown: a ring filling round the dial over the time your rigs take.
    const share = readiness(rig);
    if (share != null) {
      const around = 2 * Math.PI * 18.5;
      const fill = document.createElementNS(NS, "circle");
      fill.setAttribute("cx", "20"); fill.setAttribute("cy", "20"); fill.setAttribute("r", "18.5");
      fill.setAttribute("class", "timer");
      fill.setAttribute("stroke-dasharray", `${(around * share).toFixed(2)} ${around.toFixed(2)}`);
      fill.setAttribute("transform", "rotate(-90 20 20)");
      svg.appendChild(fill);
    }
    if (rig.here) {
      const dot = document.createElementNS(NS, "circle");
      dot.setAttribute("cx", "20"); dot.setAttribute("cy", "20"); dot.setAttribute("r", "6");
      dot.setAttribute("class", "here-dot");
      svg.appendChild(dot);
      return svg;
    }
    const needle = document.createElementNS(NS, "path");
    needle.setAttribute("d", "M20 7.5 L23.6 15.5 L20 13.8 L16.4 15.5 Z M20 20 L20 13.8");
    needle.setAttribute("class", "needle");
    needle.setAttribute("transform", `rotate(${number(rig.relative)} 20 20)`);
    const hub = document.createElementNS(NS, "circle");
    hub.setAttribute("cx", "20"); hub.setAttribute("cy", "20"); hub.setAttribute("r", "2.6");
    hub.setAttribute("class", "hub");
    svg.append(needle, hub);
    return svg;
  }

  // A hold: how full it is, never what's in it (that's the Cargo overlay).
  function hold(row) {
    const used = number(row.used), capacity = Math.max(0, number(row.capacity));
    const share = capacity ? Math.min(1, used / capacity) : 0;
    const full = !row.partial && share >= 1, nearly = !row.partial && share >= 0.9;
    const item = node("li", `hold${full ? " full" : nearly ? " nearly" : ""}${row.partial ? " partial" : ""}`);
    const bar = node("span", "bar");
    const fill = node("i");
    fill.style.setProperty("--fill", share.toFixed(3));
    bar.appendChild(fill);
    item.append(node("span", "hold-name", String(row.name || "")), bar,
      node("b", "hold-used", `${row.partial ? "+" : ""}${used} / ${capacity} t`),
      node("small", "hold-free", row.partial ? "THIS TRIP" : full ? "FULL" : `${number(row.free)} FREE`));
    return item;
  }

  // -- the sections ------------------------------------------------------------------
  function guide(data) {
    if (!data) return "";
    const pips = Array.from({length: number(data.total)}, (_, index) =>
      `<i class="${index < number(data.step) - 1 ? "done" : index === number(data.step) - 1 ? "now" : ""}"></i>`).join("");
    return `<header><h4>GUIDE ${number(data.step)}/${number(data.total)}</h4><span class="pips">${pips}</span></header>
      <div class="guide-title">${escapeHtml(data.title)}</div>
      <div class="guide-detail">${escapeHtml(data.detail)}</div>
      ${data.key ? `<span class="guide-key">${escapeHtml(data.key)}</span>` : ""}
      ${data.next ? `<div class="guide-next">then: ${escapeHtml(data.next)}</div>` : ""}`;
  }

  function deposit(data) {
    if (!data) return "";
    const near = data.near;
    const rows = near?.rig ? [
      ["RIG", `<span style="color:${colourOf(near.commodity)}">#${near.rig}${near.commodity ? ` · ${escapeHtml(near.commodity)}` : ""}</span>`],
      ["RANGE", `${turn(near.bearing)} ${Draw.metres(number(near.distance))}`],
      ["REFINED", near.tonnes ? `${number(near.tonnes)} t` : "nothing yet"],
      ["WORTH", near.value ? `~${credits(near.value)} CR` : "—"],
      ["DEPOSIT", "<span class=\"dim\">not marked: MARK DEPOSIT</span>"],
    ] : near ? [
      ["MINERAL", `<span style="color:${colourOf(near.commodity, near.depleted)}">${escapeHtml(near.commodity)}</span>`],
      ["RANGE", `${turn(near.bearing)} ${Draw.metres(number(near.distance))}`],
      ["RIGS", near.rigs || "—"], ["DENSITY", escapeHtml(near.density || "—")],
      ["AMOUNT", near.depleted ? `<span class="${near.due ? "yellow" : "dim"}">${escapeHtml(near.regrowth || "Depleted")}</span>` : escapeHtml(near.amount || "—")],
      ["EST. VALUE", near.value ? `~${credits(near.value)} CR` : "—"],
    ] : [["MINERAL", "<span class=\"dim\">none marked within 500 m</span>"]];
    return `<header><h4>MINERAL DEPOSIT</h4><em>${sections.signal != null ? `SIGNAL ${escapeHtml(sections.signal)}` : ""}</em></header>
      <dl class="rows pairs">${rows.map(([label, value]) => `<dt>${label}</dt><dd>${value}</dd>`).join("")}</dl>
      ${number(data.refined) ? `<div class="telemetry">REFINED HERE <b>${number(data.refined)} t</b>${data.refined_value ? ` · ~${credits(data.refined_value)} CR` : ""}</div>` : ""}`;
  }

  function targets(data) {
    if (!data) return "";
    const rows = (data.rows || []).map((row) => `<li class="${row.depleted ? "mined" : ""}" style="color:${colourOf(row.commodity, row.depleted)}">
        <span>${turn(row.bearing)} ${escapeHtml(row.commodity)}</span><b>${row.depleted ? "mined" : `${Draw.metres(number(row.distance))}${row.rigs ? ` ${row.rigs}R` : ""}`}</b></li>`).join("");
    const most = Math.max(1, ...(data.bars || []).map((bar) => number(bar.credits)));
    const bars = (data.bars || []).length ? `<div class="bars">${data.bars.map((bar) =>
      `<div><i style="height:${Math.max(4, number(bar.credits) / most * 100).toFixed(0)}%;background:${colourOf(bar.commodity)}"></i><small>${escapeHtml(String(bar.commodity).toUpperCase().slice(0, 7))}</small></div>`).join("")}</div>` : "";
    return `<header><h4>NEAREST</h4></header>
      ${rows ? `<ul class="list">${rows}</ul>` : `<div class="dim">Nothing marked here yet: MARK DEPOSIT on each one you find.</div>`}${bars}${data.refined && bars ? `<div class="dim">refined here so far, at what it sells for</div>` : ""}`;
  }

  function status(data) {
    if (!data) return "";
    const value = data.credits ? `~${credits(data.credits)} CR${data.unpriced ? ` · +${data.unpriced} unpriced` : ""}`
      : data.per_rig ? "—" : "after a few rigs worked";
    const lines = [`<dl class="rows pairs"><dt>EST. VALUE</dt><dd>${value}</dd><dt>DRIVE</dt><dd>${Draw.metres(number(data.route_m))}</dd>
      ${data.per_rig ? `<dt>A RIG GIVES</dt><dd>~${Math.round(number(data.per_rig))} t (your rigs)</dd>` : ""}</dl>`];
    // The rig radar's word, unless the guide is already saying it.
    if (data.words && sections.guide?.detail !== data.words) lines.push(`<div class="line ${escapeHtml(data.tone)}">${escapeHtml(data.words)}</div>`);
    for (const group of data.groups || []) {
      lines.push(`<div class="line yellow">PATCH ${group.n} · ${group.rigs}R${group.cr_per_h ? ` · ~${credits(group.cr_per_h)} CR/H` : ""} · ${turn(group.bearing)} ${Draw.metres(number(group.distance))}</div>`);
    }
    return `<header><h4>STATUS</h4><em>${number(data.deposits)} DEP · ${number(data.rigs)}R</em></header>${lines.join("")}`;
  }

  // Back in the ship: what the run gave, what's still out, and what's next.
  function aboardCard(data) {
    if (!data) return "";
    const taken = (data.taken || []).map((row) => `<li style="color:${colourOf(row.commodity)}"><span>${escapeHtml(row.commodity)}</span><b>${number(row.t)} t</b></li>`).join("");
    const out = (data.out || []).map((rig) => `<div class="line red">RIG ${rig.slot} STILL OUT · ${distance(rig.distance_m)}${rig.commodity ? ` · ${escapeHtml(String(rig.commodity).toUpperCase())}` : ""}</div>`).join("");
    return `<header><h4>BACK ABOARD</h4><em>${data.minutes != null ? `${number(data.minutes)} MIN RUN` : ""}</em></header>
      <dl class="rows pairs"><dt>REFINED</dt><dd>${number(data.refined_t)} t</dd><dt>RIGS OUT</dt><dd>${(data.out || []).length || "none"}</dd></dl>
      ${taken ? `<ul class="list">${taken}</ul>` : ""}${out}
      ${data.site ? `<div class="telemetry">SITE <b>${escapeHtml(data.site.name)}</b>${data.site.swept != null ? ` · ${Math.floor(number(data.site.swept))}% swept` : ""} · saved</div>` : ""}
      ${data.history ? `<div class="telemetry">RUN <b>${number(data.history.run)}</b> HERE${data.tph ? ` · <b>${number(data.tph)} T/H</b>` : ""}${data.history.best_tph ? ` · BEST BEFORE ${number(data.history.best_tph)} T/H` : ""}</div>` : ""}
      <div class="guide-next">next: ${escapeHtml(data.next)}</div>`;
  }

  // The survey, the rig plan, the best patch, the next deposit and the planning circle.
  function factLines(facts) {
    const lines = [];
    if (facts.tracing) lines.push("TRACING THE DEPOSIT · DRIVE BACK TO THE START");
    if (facts.survey?.edge) lines.push(`SURVEY ${Math.floor(number(facts.survey.percent))}%${facts.survey.next ? ` · NEXT STOP ${distance(facts.survey.next.distance)} ${facts.survey.next.compass || ""}` : " · SWEPT"}`);
    else if (facts.survey) lines.push(`SURVEY · CENTRE ${distance(facts.survey.centre_m)} ${facts.survey.centre_compass || ""} · ${facts.survey.edge_ok ? "MARK THE EDGE WHEN YOU'RE THERE" : "DRIVE OUT TO ITS EDGE"}`);
    if (facts.plan) lines.push(facts.plan.next ? `PLAN P${facts.plan.next.n} ${number(facts.plan.next.distance) < 20 ? "HERE" : `${distance(facts.plan.next.distance)} ${facts.plan.next.compass || ""}`} · ${number(facts.plan.filled)}/${number(facts.plan.pins)} DOWN` : `PLAN DONE · ${number(facts.plan.pins)} RIGS`);
    if (facts.patch) lines.push(`BEST PATCH ${number(facts.patch.distance) < 40 ? "HERE" : `${distance(facts.patch.distance)} ${facts.patch.compass || ""}`} · ${facts.patch.marked ? `${number(facts.patch.rigs)} RIGS` : `${number(facts.patch.pulses)} PULSES`}`);
    if (facts.deposits?.next) lines.push(`NEXT DEPOSIT ${String(facts.deposits.next.commodity).toUpperCase()} ${distance(facts.deposits.next.distance)} ${facts.deposits.next.compass || ""}`);
    if (facts.rig_spot && number(facts.rig_spot.distance) >= 10) lines.push(`NEXT RIG SPOT ${distance(facts.rig_spot.distance)} ${facts.rig_spot.compass || ""}`);
    if (facts.circle) lines.push(number(facts.circle.room) >= 0 ? `PLANNING CIRCLE · ${distance(facts.circle.room)} TO ITS EDGE` : `OUTSIDE THE PLANNING CIRCLE BY ${distance(-number(facts.circle.room))}`);
    return lines;
  }

  function render(snapshot = {}) {
    VoidCompassOverlay.applyTheme(root, snapshot.theme || {}, snapshot.effects || {});
    VoidCompassOverlay.fitToWindow(root, 420, snapshot.effects || {});
    const model = snapshot.rigs || null;
    root.classList.toggle("empty", !model);
    if (!model) return;
    sections = model.sections || {};
    byId("rigs-body").textContent = String(model.body || "").toUpperCase();
    byId("rigs-count").textContent = model.aboard && !number(model.tracked) ? "IN THE SHIP" : `${number(model.tracked)} OUT`;
    part("rigs-aboard", aboardCard(model.aboard));
    byId("rigs-dials").hidden = Boolean(model.aboard) && !number(model.tracked);
    byId("rigs-dials").replaceChildren(...(model.slots || []).map((rig) => {
      const share = readiness(rig);
      const ready = share != null && share >= 1;
      const item = node("li", `dial${rig.tracked ? "" : " idle"}${rig.next ? " nearest" : ""}${rig.here ? " at" : ""}${ready ? " ready" : ""}`);
      // What it's working on one line and its tonnes and time down on the
      // next, each cut to the dial's width: never across the next dial.
      const working = rig.tracked && rig.commodity ? String(rig.commodity).toUpperCase() : "";
      const left = share == null ? 0 : Math.ceil(number(rig.ready_s) * (1 - share));
      const clock = share == null ? age(rig.at) : ready ? "READY" : `${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")}`;
      const since = rig.tracked ? [number(rig.tonnes) ? `${number(rig.tonnes)}T` : "", clock].filter(Boolean).join(" · ") : "";
      item.append(node("span", "slot", `#${rig.slot}`), dial(rig),
        node("b", "distance", rig.tracked ? (rig.here ? "HERE" : distance(rig.distance_m)) : "--"),
        node("small", "working", working), node("small", "age", since));
      if (working) item.title = working;
      return item;
    }));
    const order = (model.order || []).map((slot) => `#${slot}`);
    byId("rigs-order").textContent = order.length > 1 ? `COLLECT ▸ ${order.join(" → ")}` : "";
    byId("rigs-order").hidden = order.length < 2;
    const on = new Set(sections.sections || []);
    const hazard = byId("rigs-hazard");
    hazard.hidden = !sections.hazard;
    hazard.textContent = sections.hazard ? `⚠ ${sections.hazard}` : "";
    part("rigs-guide", on.has("guide") ? guide(sections.guide) : "");
    part("rigs-deposit", on.has("deposit") ? deposit(sections.deposit) : "");
    part("rigs-targets", on.has("targets") ? targets(sections.targets) : "");
    part("rigs-status", on.has("status") ? status(sections.status) : "");
    const lines = factLines(model.survey || {});
    const survey = byId("rigs-survey");
    survey.replaceChildren(...lines.map((line) => node("li", "", line.trim())));
    survey.hidden = !lines.length;
    const holds = (model.holds || []).filter((row) => number(row.capacity) > 0);
    byId("rigs-holds").replaceChildren(...holds.map(hold));
    byId("rigs-holds").hidden = !holds.length;
    byId("rigs-hint").textContent = String(model.hint || "");
    byId("rigs-hint").hidden = !model.hint;
  }

  function contentHeight() {
    return VoidCompassOverlay.designHeight(root, 130);
  }

  window.__rigtracker = {sections: () => sections};
  const poller = VoidCompassOverlay.startPolling({token, overlay, render, contentHeight, interval: 250});
  // Each rig's countdown keeps moving while you stand still.
  setInterval(() => poller?.rerender?.(), 1000);
})();
