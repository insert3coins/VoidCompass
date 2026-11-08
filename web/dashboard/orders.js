// Crew Orders (5.7.7): the officers ask things of you. Offers waiting for
// your answer, the orders you're on, the campaign under way, each officer's
// record with you (standing, Order Files, ribbons), and the log. Tabs are
// client-only; every button sends a command and the next snapshot redraws.

const TABS = [["orders", "ORDERS"], ["campaign", "CAMPAIGN"], ["record", "SERVICE RECORD"], ["log", "LOG"]];
const OFFICERS = ["watcher", "aster", "axiom", "meridian", "lyra"];
const GLYPHS = {watcher: "◉", aster: "✶", axiom: "⬡", meridian: "⌖", lyra: "◈"};
let tab = "orders";
// The officer open on the SERVICE RECORD tab (client-only, like the tabs).
let recordOfficer = "";
let lastMarkup = "";
// The last snapshot and UI, so a tab click redraws at once (5.7.7).
let lastData = null;
let lastUi = null;

const n = (value) => Number.isFinite(Number(value)) ? Number(value) : 0;

function ago(ts) {
  if (!ts) return "";
  const seconds = Date.now() / 1000 - n(ts);
  if (seconds < 90) return "just now";
  if (seconds < 3600) return `${Math.round(seconds / 60)} min ago`;
  if (seconds < 172800) return `${Math.round(seconds / 3600)} h ago`;
  return `${Math.round(seconds / 86400)} days ago`;
}

function until(ts) {
  if (!ts) return "";
  const seconds = n(ts) - Date.now() / 1000;
  if (seconds <= 0) return "expiring";
  if (seconds < 3600) return `${Math.max(1, Math.round(seconds / 60))} min left`;
  if (seconds < 172800) return `${Math.round(seconds / 3600)} h left`;
  return `${Math.round(seconds / 86400)} days left`;
}

// 8 November: the page was rebuilt whenever a minute ticked over or the
// status line changed ("Someone's talking" comes and goes with every line),
// which closed open sections and swapped buttons out from under the pointer.
// Times and the status line now change in place; the rest only on real news.
const stamp = (kind, ts) => ts ? `<time data-ord-${kind}="${Math.round(n(ts))}"></time>` : "";
function fillTimes(root) {
  for (const node of root.querySelectorAll("[data-ord-ago]")) {
    const text = ago(node.dataset.ordAgo);
    if (node.textContent !== text) node.textContent = text;
  }
  for (const node of root.querySelectorAll("[data-ord-until]")) {
    const text = until(node.dataset.ordUntil);
    if (node.textContent !== text) node.textContent = text;
  }
}

function send(ui, operation, extra = {}) {
  return ui.command("workspace", {page: "orders", operation, ...extra});
}

function officerTag(officer, name, esc, onWatch) {
  return `<span class="ord-officer ord-${esc(officer)}"><i>${GLYPHS[officer] || "•"}</i>${esc(name || officer)}${onWatch === officer ? "<em>ON WATCH</em>" : ""}</span>`;
}

function bar(fraction) {
  const pct = Math.round(Math.max(0, Math.min(1, n(fraction))) * 100);
  return `<span class="ord-bar" role="progressbar" aria-valuenow="${pct}" aria-valuemin="0" aria-valuemax="100"><i style="--w:${pct}%"></i></span>`;
}

function objectivesList(order, esc) {
  if (!order.objectives || !order.objectives.length) {
    return `<p class="ord-dim">${order.size === "campaign" ? "This stage is waiting for a target." : "No objectives yet."}</p>`;
  }
  return `<ul class="ord-objectives">${order.objectives.map((row) =>
    `<li class="${row.done ? "done" : ""}"><b>${row.done ? "✓" : "○"}</b><span>${esc(row.text)}</span>${row.done ? "" : bar(row.fraction)}</li>`).join("")}</ul>`;
}

function whyList(order, esc) {
  const rows = order.why || [];
  if (!rows.length) return "";
  return `<details class="ord-why" data-ord-key="why:${esc(order.id)}"><summary>WHY</summary><ul>${rows.map((row) =>
    `<li><span>${esc(row.text)}</span><small>${esc(row.source)}${row.at ? ` · ${stamp("ago", row.at)}` : ""}</small></li>`).join("")}</ul></details>`;
}

function target(order, esc) {
  const where = order.target || {};
  const bits = [where.station, where.body, where.system || where.region].filter(Boolean);
  if (!bits.length && !where.distance) return "";
  return `<p class="ord-target"><b>TARGET</b> ${esc(bits.join(" · "))}${where.distance ? ` <em>${esc(where.distance)}</em>` : ""}</p>`;
}

function lastLine(order, data, esc) {
  const line = order.last_line;
  if (!line || !line.text) return "";
  const name = (data.record?.[line.speaker] || {}).name || line.speaker;
  return `<blockquote class="ord-line ord-${esc(line.speaker)}"><p>${esc(line.text)}</p><cite>${esc(name)}</cite></blockquote>`;
}

function offerCard(order, data, esc) {
  const plot = order.target && (order.target.system || order.target.plot);
  return `<article class="ord-card offer ord-${esc(order.officer)}">
    <header>${officerTag(order.officer, order.officer_name, esc, data.on_watch)}<span class="ord-size">${esc(order.size === "long" ? "LONG ORDER" : order.size === "campaign" ? "CAMPAIGN" : "FIELD ORDER")}</span>
      <span class="ord-time">${order.later ? "ON THE BOARD · " : ""}${stamp("until", order.expires_at)}</span></header>
    <h3>${esc(order.title)}</h3>
    <p class="ord-brief">${esc(order.brief)}</p>
    ${lastLine(order, data, esc)}
    ${order.size === "campaign" ? stageTrack(order, esc) : objectivesList(order, esc)}
    ${target(order, esc)}${whyList(order, esc)}
    <footer><button type="button" class="cockpit-button primary" data-orders-op="accept" data-id="${esc(order.id)}">ACCEPT</button>
      ${order.later ? "" : `<button type="button" class="cockpit-button" data-orders-op="later" data-id="${esc(order.id)}">LATER</button>`}
      <button type="button" class="cockpit-button" data-orders-op="decline" data-id="${esc(order.id)}">DECLINE</button>
      ${plot ? `<button type="button" class="cockpit-button ghost" data-orders-op="plot" data-id="${esc(order.id)}" title="Copy the system name">COPY SYSTEM</button>` : ""}</footer>
  </article>`;
}

function activeCard(order, data, esc) {
  const plot = order.target && (order.target.system || order.target.plot);
  return `<article class="ord-card active ord-${esc(order.officer)}">
    <header>${officerTag(order.officer, order.officer_name, esc, data.on_watch)}<span class="ord-size">${esc(order.size === "long" ? "LONG ORDER" : "FIELD ORDER")}</span>
      <span class="ord-time">${stamp("until", order.expires_at)}</span></header>
    <h3>${esc(order.title)}</h3>
    <div class="ord-progress">${bar(order.progress)}<b>${Math.round(n(order.progress) * 100)}%</b></div>
    ${objectivesList(order, esc)}
    ${target(order, esc)}${lastLine(order, data, esc)}${whyList(order, esc)}
    <footer>${plot ? `<button type="button" class="cockpit-button" data-orders-op="plot" data-id="${esc(order.id)}">COPY SYSTEM</button>` : ""}
      <button type="button" class="cockpit-button ghost danger" data-orders-op="abandon" data-id="${esc(order.id)}">CANCEL ORDER</button></footer>
  </article>`;
}

function stageTrack(order, esc) {
  const stages = order.stages || [];
  return `<ol class="ord-stages">${stages.map((stage, index) =>
    `<li class="${stage.done ? "done" : ""}${stage.current ? " current" : ""} ord-${esc(stage.officer)}"><i>${stage.done ? "✓" : index + 1}</i>
      <span><b>${esc(stage.title)}</b><small>${esc(GLYPHS[stage.officer] || "")} ${esc(stage.chosen ? `chose ${stage.chosen}` : stage.officer)}</small></span></li>`).join("")}</ol>`;
}

function ordersTab(data, esc) {
  const offered = data.offered || [];
  const active = (data.active || []).filter((row) => row.size !== "campaign");
  const waiting = offered.length ? `<section class="ord-section"><h4>WAITING FOR YOUR ANSWER</h4><div class="ord-grid">${offered.map((row) => offerCard(row, data, esc)).join("")}</div></section>` : "";
  const running = active.length ? `<section class="ord-section"><h4>UNDER WAY · ${active.length} OF 3 FIELD ORDERS</h4><div class="ord-grid">${active.map((row) => activeCard(row, data, esc)).join("")}</div></section>`
    : `<section class="ord-section"><h4>UNDER WAY</h4><p class="ord-empty">No orders under way. The crew offers them as you fly${data.frequency === "off" ? " (offers are off in Settings)" : ""}, or ask now.</p></section>`;
  return waiting + running;
}

function campaignTab(data, esc) {
  const campaign = (data.active || []).find((row) => row.size === "campaign");
  const offered = (data.offered || []).find((row) => row.size === "campaign");
  if (!campaign) {
    return `<section class="ord-section"><h4>CAMPAIGN</h4><p class="ord-empty">No campaign under way.${offered ? " One is waiting on the ORDERS tab." : " Campaigns are offered now and then: several stages, handed between officers, with targets drawn from your own record."}</p></section>`;
  }
  const choice = (campaign.stages || []).find((stage) => stage.current && stage.choice);
  const choices = choice ? `<div class="ord-choice"><h4>YOUR CALL</h4>${choice.choice.map((option) =>
    `<button type="button" class="cockpit-button primary" data-orders-op="choose" data-id="${esc(campaign.id)}" data-option="${esc(option.id)}">${esc(option.label)}</button>`).join("")}</div>` : "";
  const scenes = (campaign.scenes || []).slice().reverse().map((scene) => `<div class="ord-scene"><small>${stamp("ago", scene.at)}</small>${scene.lines.map((line) =>
    `<p class="ord-${esc(line.speaker)}"><b>${esc((data.record?.[line.speaker] || {}).name || line.speaker)}</b>${esc(line.text)}</p>`).join("")}</div>`).join("");
  return `<section class="ord-section ord-campaign ord-${esc(campaign.officer)}">
    <header><h3>${esc(campaign.title)}</h3>${officerTag(campaign.officer, campaign.officer_name, esc, data.on_watch)}<b>${Math.round(n(campaign.progress) * 100)}%</b></header>
    <p class="ord-brief">${esc(campaign.brief)}</p>
    ${stageTrack(campaign, esc)}
    <div class="ord-stage-now"><h4>THIS STAGE</h4>${choices}${objectivesList(campaign, esc)}${target(campaign, esc)}${lastLine(campaign, data, esc)}</div>
    ${scenes ? `<div class="ord-scenes"><h4>ON THE BRIDGE</h4>${scenes}</div>` : ""}
    <footer><button type="button" class="cockpit-button ghost danger" data-orders-op="abandon" data-id="${esc(campaign.id)}">ABANDON CAMPAIGN</button></footer>
  </section>`;
}

// 8 November: the record was a grid of cards that left holes wherever one
// Order File was open. Now a roster of the five, and the one you pick in full.
function recordTab(data, esc) {
  const records = data.record || {};
  const chosen = OFFICERS.includes(recordOfficer) ? recordOfficer : OFFICERS.includes(data.on_watch) ? data.on_watch : "watcher";
  const roster = OFFICERS.map((officer) => {
    const row = records[officer] || {};
    const passages = (row.file || {}).passages || [];
    const told = passages.filter((passage) => passage.told).length;
    const span = n(row.next_at) - n(row.standing_from);
    const toward = row.next_standing && span > 0 ? (n(row.done) - n(row.standing_from)) / span : 1;
    const next = row.next_standing ? `${Math.max(0, n(row.next_at) - n(row.done))} more for ${esc(row.next_standing)}` : "Highest standing";
    return `<li><button type="button" class="ord-roster-row ord-${esc(officer)}${officer === chosen ? " chosen" : ""}" data-orders-officer="${esc(officer)}" aria-pressed="${officer === chosen}">
      <i>${GLYPHS[officer]}</i><span class="ord-roster-name"><b>${esc(row.name || officer)}</b>${data.on_watch === officer ? "<em>ON WATCH</em>" : ""}</span>
      <strong>${esc(row.standing || "")}</strong>
      ${bar(toward)}<small>${next}</small><small class="ord-roster-files">${told}/${passages.length} FILES</small></button></li>`;
  }).join("");
  const row = records[chosen] || {};
  const file = row.file || {passages: []};
  const passages = file.passages.map((passage) => passage.told
    ? `<li class="told"><b>${esc(passage.number)}</b><p>${esc(passage.text)}</p></li>`
    : `<li class="locked"><b>${esc(passage.number)}</b><p>After ${esc(passage.needs)} order${passage.needs === 1 ? "" : "s"} for ${esc(row.name)}.</p></li>`).join("");
  const muted = (row.muted || []).length ? `<p class="ord-muted">Not offering: ${esc(row.muted.join(", "))} <button type="button" class="ord-link" data-orders-op="unmute" data-officer="${esc(chosen)}">OFFER AGAIN</button></p>` : "";
  const stats = [["DONE", row.done], ["CAMPAIGNS", row.campaigns], ["SIDED WITH", row.sided], ["DECLINED", row.declined], ["CANCELLED", row.abandoned]]
    .map(([label, value]) => `<div><dt>${label}</dt><dd>${n(value)}</dd></div>`).join("");
  const dossier = `<article class="ord-dossier ord-${esc(chosen)}">
    <header>${officerTag(chosen, row.name, esc, data.on_watch)}<strong>${esc(row.standing || "")}</strong></header>
    <dl>${stats}</dl>${muted}
    <section class="ord-file"><h4>ORDER FILES · ${esc(String(file.title || "").toUpperCase())}</h4><ol>${passages}</ol></section>
  </article>`;
  // Twelve for the crew as a whole (earned first), then each officer's Right
  // Hand in a row of five: whole rows, no ragged end.
  const all = data.ribbons || [];
  const earnedCount = all.filter((ribbon) => ribbon.at).length;
  const hand = (ribbon) => String(ribbon.id || "").startsWith("right_hand_");
  const ribbon = (row) => {
    const theme = row.theme ? (row.at ? `Postcard theme: ${row.theme}` : `Unlocks the ${row.theme} postcard theme`) : "";
    const officer = hand(row) ? ` ord-${esc(String(row.id).slice(11))}` : "";
    return `<li class="${row.at ? "earned" : ""}${officer}" title="${esc([row.for, theme].filter(Boolean).join(". "))}"><i></i><b>${esc(row.name)}</b><small>${row.at ? stamp("ago", row.at) : esc(row.for)}</small>${theme ? `<em>${esc(theme)}</em>` : ""}</li>`;
  };
  const crewWide = all.filter((row) => !hand(row));
  const ribbons = `<ul class="ord-ribbons">${[...crewWide.filter((row) => row.at), ...crewWide.filter((row) => !row.at)].map(ribbon).join("")}</ul>
    <h4 class="ord-subhead">RIGHT HAND · ONE FOR EACH OFFICER</h4><ul class="ord-ribbons hands">${all.filter(hand).map(ribbon).join("")}</ul>`;
  // 5.7.7: each finished campaign, looked back on a few hours later.
  const after = (data.after || []).map((scene) => `<div class="ord-scene"><small>${esc(String(scene.title || "").toUpperCase())} · ${stamp("ago", scene.at)}</small>${(scene.lines || []).map((line) =>
    `<p class="ord-${esc(line.speaker)}"><b>${esc((records[line.speaker] || {}).name || line.speaker)}</b>${esc(line.text)}</p>`).join("")}</div>`).join("");
  return `<section class="ord-section"><h4>EACH OFFICER'S RECORD WITH YOU</h4>
      <div class="ord-service"><ul class="ord-roster">${roster}</ul>${dossier}</div></section>
    <section class="ord-section"><h4>COMMENDATIONS · ${earnedCount} OF ${all.length} EARNED</h4>${ribbons}</section>
    <section class="ord-section"><h4>AFTER THE CAMPAIGNS</h4>${after ? `<div class="ord-scenes">${after}</div>` : `<p class="ord-empty">When a campaign is done, the crew looks back on it a few hours later, in a quiet moment. Those talks are kept here.</p>`}</section>`;
}

function logTab(data, esc) {
  const rows = data.history || [];
  if (!rows.length) return `<section class="ord-section"><h4>LOG</h4><p class="ord-empty">Nothing in the log yet.</p></section>`;
  const label = {done: "DONE", declined: "DECLINED", abandoned: "CANCELLED", expired: "NOT ANSWERED", lapsed: "LAPSED", overtaken: "OVERTAKEN"};
  return `<section class="ord-section"><h4>LOG</h4><ol class="ord-log">${rows.map((row) =>
    `<li class="ord-${esc(row.officer)} ${esc(row.status)}"><span class="ord-status">${esc(label[row.status] || row.status)}</span>
      <b>${esc(row.title)}</b><small>${esc((data.record?.[row.officer] || {}).name || row.officer)} · ${stamp("ago", row.closed_at)}</small>
      ${row.objectives && row.objectives.length ? `<em>${esc(row.objectives.join(" · "))}</em>` : ""}</li>`).join("")}</ol></section>`;
}

export function renderOrders(data, ui) {
  const root = ui.byId("orders-workspace");
  if (!root) return;
  lastData = data;
  lastUi = ui;
  const esc = ui.escapeHtml;
  root.classList.remove("loading-panel");
  if (!data || data.enabled === false) {
    const markup = `<div class="ord-off"><h3>CREW ORDERS ARE OFF</h3><p>Turn them on in Settings, under Crew Orders, and the officers will start asking things of you.</p>
      <button type="button" class="cockpit-button" data-page="settings">SETTINGS</button></div>`;
    if (markup !== lastMarkup) root.innerHTML = lastMarkup = markup;
    return;
  }
  const counts = {orders: (data.offered || []).length + (data.active || []).filter((row) => row.size !== "campaign").length,
    campaign: (data.active || []).some((row) => row.size === "campaign") ? 1 : 0};
  const tabs = TABS.map(([key, label]) => `<button type="button" role="tab" aria-selected="${key === tab}" class="${key === tab ? "active" : ""}" data-orders-tab="${key}">${label}${counts[key] ? `<b>${counts[key]}</b>` : ""}</button>`).join("");
  const crew = OFFICERS.map((officer) => {
    const row = (data.record || {})[officer] || {};
    return `<li class="ord-${esc(officer)}${data.on_watch === officer ? " on-watch" : ""}"><i>${GLYPHS[officer]}</i><span><b>${esc(row.name || officer)}</b><small>${esc(row.standing || "")} · ${n(row.done)} done</small></span></li>`;
  }).join("");
  const body = tab === "campaign" ? campaignTab(data, esc) : tab === "record" ? recordTab(data, esc) : tab === "log" ? logTab(data, esc) : ordersTab(data, esc);
  const markup = `<div class="ord-page">
    <div class="ord-bridge"><ul class="ord-crew">${crew}</ul>
      <div class="ord-actions"><span class="ord-status-line" role="status"></span><span class="ord-pace">${esc((data.frequencies || {})[data.frequency] || "Offers off")}${data.online ? "" : " · searches off"}</span>
        <button type="button" class="cockpit-button primary" data-orders-op="ask">ASK FOR ORDERS</button></div></div>
    <nav class="ord-tabs" role="tablist" aria-label="Crew Orders">${tabs}</nav>
    <div class="ord-body">${body}</div></div>`;
  if (markup !== lastMarkup) {
    const open = new Map([...root.querySelectorAll("details[data-ord-key]")].map((node) => [node.dataset.ordKey, node.open]));
    root.innerHTML = lastMarkup = markup;
    for (const node of root.querySelectorAll("details[data-ord-key]")) {
      if (open.has(node.dataset.ordKey)) node.open = open.get(node.dataset.ordKey);
    }
  }
  fillTimes(root);
  showStatus(root, data);
}

// A command's outcome comes back in the snapshot and shows for a few
// seconds; otherwise, why no offer is coming just now.
let statusTimer = 0;
function showStatus(root, data) {
  const line = root.querySelector(".ord-status-line");
  if (!line) return;
  const age = Date.now() / 1000 - n(data.notice?.at);
  const notice = data.notice && age < 8 ? data.notice : null;
  const text = notice ? String(notice.text || "") : String(data.why || "");
  if (line.textContent !== text) line.textContent = text;
  line.className = `ord-status-line ${notice ? `ord-notice${notice.ok ? "" : " warn"}` : text ? "ord-why-now" : ""}`.trim();
  window.clearTimeout(statusTimer);
  if (notice) statusTimer = window.setTimeout(() => lastData && showStatus(root, lastData), (8 - age) * 1000 + 50);
}

export function handleOrdersClick(event, ui) {
  const tabButton = event.target.closest("[data-orders-tab]");
  if (tabButton) {
    tab = tabButton.dataset.ordersTab;
    lastMarkup = "";
    if (lastData) renderOrders(lastData, lastUi || ui);
    Promise.resolve(send(ui, "view", {view: tab})).catch(() => {});
    return true;
  }
  const officer = event.target.closest("[data-orders-officer]");
  if (officer) {
    recordOfficer = officer.dataset.ordersOfficer;
    lastMarkup = "";
    if (lastData) renderOrders(lastData, lastUi || ui);
    return true;
  }
  const button = event.target.closest("[data-orders-op]");
  if (!button) return false;
  const operation = button.dataset.ordersOp;
  if (operation === "abandon" && !window.confirm("Cancel this order? The officer will remember, gently.")) return true;
  button.disabled = true;
  Promise.resolve(send(ui, operation, {id: button.dataset.id || "", option: button.dataset.option || "", officer: button.dataset.officer || ""}))
    .catch(() => {})
    .finally(() => { button.disabled = false; });
  return true;
}
