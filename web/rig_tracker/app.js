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

  // How far a rig is towards ready, 0 to 1, once your rigs have taught how
  // long they take (rig.ready_s); null before then, or while you're
  // collecting from it.
  const readiness = (rig) => rig.tracked && !rig.collecting && number(rig.ready_s) > 0
    ? Math.max(0, Math.min(1, (Date.now() / 1000 - number(rig.fill_from || rig.at)) / number(rig.ready_s))) : null;
  const clockText = (seconds) => {
    const s = Math.max(0, Math.round(seconds));
    return s >= 3600 ? `${Math.floor(s / 3600)}:${String(Math.floor(s / 60) % 60).padStart(2, "0")}h` : `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  };

  function svg(tag, attrs) {
    const element = document.createElementNS(NS, tag);
    for (const [name, value] of Object.entries(attrs)) element.setAttribute(name, String(value));
    return element;
  }

  // The rig's ring: its number in the middle, filling round to READY, and a
  // marker riding round the outside pointing the way it lies from where you
  // face (top is straight ahead), as the old dials' needle did.
  function ring(rig, share) {
    const box = svg("svg", {viewBox: "0 0 52 52", class: "rig-ring", "aria-hidden": "true"});
    box.append(svg("circle", {cx: 26, cy: 26, r: 17, class: "track"}));
    if (share != null) {
      const around = 2 * Math.PI * 17;
      box.append(svg("circle", {cx: 26, cy: 26, r: 17, class: "fill", transform: "rotate(-90 26 26)",
        "stroke-dasharray": `${(around * share).toFixed(2)} ${around.toFixed(2)}`}));
    }
    if (rig.here) box.append(svg("circle", {cx: 26, cy: 26, r: 14, class: "here"}));
    else box.append(svg("path", {d: "M26 -2 L35.5 12 L26 8 L16.5 12 Z", class: "bug", transform: `rotate(${number(rig.relative)} 26 26)`}));
    const label = svg("text", {x: 26, y: 27, class: "num", "text-anchor": "middle", "dominant-baseline": "middle"});
    label.textContent = String(rig.slot);
    box.append(label);
    return box;
  }

  // One rig out, a card two to a line: its ring, what it's working, which
  // way and how far (and its tonnes), and its clock.
  function rigRow(rig) {
    const share = readiness(rig);
    const ready = share != null && share >= 1;
    const learning = !rig.collecting && !(number(rig.ready_s) > 0);
    const state = rig.collecting ? "collecting" : ready ? "ready" : learning ? "learning" : "filling";
    const item = node("li", `rig ${state}${rig.next ? " nearest" : ""}${rig.here ? " at" : ""}`);
    const working = rig.commodity ? String(rig.commodity).toUpperCase() : "WORKING";
    const where = node("span", "rig-where");
    where.append(node("b", "", rig.here ? "HERE" : distance(rig.distance_m)));
    if (number(rig.tonnes)) where.append(node("small", "", `· ${number(rig.tonnes)} t`));
    const filled = Date.now() / 1000 - number(rig.fill_from || rig.at);
    const clock = node("span", "rig-clock");
    // This collection's tonnes as they come in, then what the last one gave.
    const haul = number(rig.haul);
    const last = haul ? `· last ${haul} t` : "";
    if (rig.collecting) clock.append(node("b", "", "COLLECTING"), node("small", "haul", `${haul} t`));
    else if (ready) clock.append(node("b", "", "READY"), node("small", "", last));
    else if (learning) clock.append(node("b", "", clockText(filled)), node("small", "", ["filling", last].filter(Boolean).join(" ")));
    else clock.append(node("b", "", clockText(number(rig.ready_s) - filled)), node("small", "", ["to ready", last].filter(Boolean).join(" ")));
    item.append(ring(rig, share), node("b", "rig-name", working), where, clock);
    item.title = `Rig ${rig.slot}: ${working}, down ${age(rig.at)}`;
    return item;
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
    const out = (model.slots || []).filter((rig) => rig.tracked);
    const list = byId("rigs-list");
    list.hidden = !out.length;
    list.replaceChildren(...out.map(rigRow));
    // The rig numbers still free, on one line rather than empty rows.
    const free = (model.slots || []).filter((rig) => !rig.tracked).map((rig) => `#${rig.slot}`);
    const freeLine = byId("rigs-free");
    freeLine.hidden = !out.length || !free.length || (Boolean(model.aboard) && !out.length);
    freeLine.textContent = free.length ? `FREE  ${free.join("  ")}` : "";
    const order = (model.order || []).map((slot) => `#${slot}`);
    byId("rigs-order").textContent = order.length > 1 ? `COLLECT ▸ ${order.join(" → ")}` : "";
    byId("rigs-order").hidden = order.length < 2;
    const on = new Set(sections.sections || []);
    const hazard = byId("rigs-hazard");
    hazard.hidden = !sections.hazard;
    hazard.textContent = sections.hazard ? `⚠ ${sections.hazard}` : "";
    part("rigs-guide", on.has("guide") ? guide(sections.guide) : "");
    part("rigs-deposit", on.has("deposit") ? deposit(sections.deposit) : "");
    // The rig radar's word, unless the guide is already saying it.
    const radar = sections.radar && sections.guide?.detail !== sections.radar.words ? sections.radar : null;
    const radarLine = byId("rigs-word");
    radarLine.hidden = !radar;
    radarLine.className = `line rig-word ${radar ? radar.tone || "" : ""}`;
    radarLine.textContent = radar ? radar.words : "";
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
