/** Commander Record in tabs (5.7.8): CMDR, FLEET & INVENTORY, MISSIONS,
 * SESSIONS and EARNINGS. The record's cards are sorted into the tabs, and the
 * books from the journal fill in the rest: a money line, the next rank, the
 * whole fleet with EDSY and Coriolis links, stored modules, missions soonest
 * first with their kills, Community Goals, vouchers held, fighting and mining
 * by login, every ring you've mined, and earnings. After ED-Outrider's CMDR
 * view (github.com/weslocke/ED-Outrider, GPLv3). No Engineering tab, by design. */

import {credits, downloadText, esc, fetchData, fixed, renderTable, toCsv} from "./explore-table.js";

const TABS = [["cmdr", "CMDR"], ["fleet", "FLEET & INVENTORY"], ["missions", "MISSIONS"], ["sessions", "SESSIONS"], ["earnings", "EARNINGS"]];
// Which tab each of the record's cards belongs on, by its heading.
const HOME = [["CAREER RANKS", "cmdr"], ["SUPERPOWER REPUTATION", "cmdr"], ["CAREER RECORDS", "cmdr"], ["EXOBIOLOGY CAREER", "cmdr"],
  ["PROFILE CUSTODY", "cmdr"], ["ON FOOT", "fleet"], ["ON-FOOT RECORD", "fleet"], ["BACKPACK", "fleet"], ["SHIP LOCKER", "fleet"],
  ["ACTIVE SHIP", "fleet"], ["STORED FLEET", "fleet"], ["OBSERVED SURFACE VEHICLES", "fleet"], ["FLEET CARRIER", "fleet"],
  ["MISSION RESPONSIBILITIES", "missions"]];
const KIND_LABELS = {exploration: "Exploration", exobiology: "Exobiology", trade: "Trade", mining: "Mining", bounties: "Bounties",
  bonds: "Combat bonds", missions: "Missions", other: "Other"};

let st = {ui: null, profile: "", book: null, earnings: null, period: "all", tab: "cmdr", loading: false, polling: 0, lastFetch: 0};

function tabOf(title) {
  const upper = String(title || "").toUpperCase();
  return (HOME.find(([prefix]) => upper.startsWith(prefix)) || [null, "cmdr"])[1];
}

function hours(seconds) {
  if (!seconds) return "";
  return seconds >= 3600 ? `${fixed(seconds / 3600, 1)} h` : `${Math.round(seconds / 60)} min`;
}

function moneyMarkup(book) {
  const m = book?.money;
  if (!m) return "";
  const cell = (label, value, detail = "") => `<article><small>${label}</small><strong>${value}</strong><span>${detail}</span></article>`;
  const v = m.vouchers;
  return `<section class="workspace-metrics cmdr-money">
    ${cell("CREDITS", m.credits !== null && m.credits !== undefined ? `${credits(m.credits)} cr` : "—")}
    ${cell("NET WORTH", m.net_worth ? `${credits(m.net_worth)} cr` : "—", "the game's Statistics")}
    ${cell("FLEET", `${credits(m.fleet_value) || "0"} cr`, `${m.ships} ship${m.ships === 1 ? "" : "s"}`)}
    ${cell("STORED MODULES", `${credits(m.modules_value) || "0"} cr`, `${m.modules} module${m.modules === 1 ? "" : "s"}`)}
    ${cell("CARRIER BALANCE", m.carrier_balance !== null && m.carrier_balance !== undefined ? `${credits(m.carrier_balance)} cr` : "—")}
    ${cell("VOUCHERS HELD", v ? `${credits(v.total)} cr` : "none", v ? `bounties ${credits(v.bounties) || 0} · bonds ${credits(v.bonds) || 0}` : "lost if you die")}
  </section>`;
}

function ranksMarkup(book) {
  const rows = (book?.ranks || []).map((row) => `<div class="cmdr-rank"><b>${esc(row.kind === "Explore" ? "Explorer" : row.kind)}</b><span>${esc(row.name)}${row.percent !== null && row.percent !== undefined ? ` · ${Math.round(row.percent)}%` : ""}</span>
    <small>${row.next ? `next: ${esc(row.next)}` : "top rank"}${row.credits_left !== undefined ? ` · about ${credits(row.credits_left)} cr of exobiology data to go (an estimate)` : ""}</small></div>`).join("");
  return rows ? `<article class="card workspace-card"><header><span>RANKS · WHAT'S NEXT</span></header><div class="cmdr-ranks">${rows}</div></article>` : "";
}

const FLEET = [
  {id: "name", label: "SHIP", cell: (r) => `<b>${esc(r.name || r.type_name || r.type)}</b>${r.current ? ` <em class="xn-here">FLYING</em>` : ""}<div class="xn-dim">${esc(r.type_name || r.type || "")}${r.ident ? ` · ${esc(r.ident)}` : ""}</div>`, sort: (r) => r.name || r.type},
  {id: "where", label: "WHERE", cell: (r) => (r.current ? "with you" : r.in_transit ? "in transit" : `${esc(r.station || "")}${r.system ? ` · ${esc(r.system)}` : ""}`), sort: (r) => r.system},
  {id: "value", label: "VALUE", cell: (r) => credits(r.value), sort: (r) => r.value, cls: "xt-num", firstDir: "desc"},
  {id: "transfer", label: "TO BRING HERE", short: "MOVE", cell: (r) => (r.transfer_cost ? `${credits(r.transfer_cost)}${r.transfer_s ? ` · ${hours(r.transfer_s)}` : ""}` : ""), sort: (r) => r.transfer_cost, cls: "xt-num", fit: 2},
  {id: "hot", label: "", cell: (r) => (r.hot ? `<span title="hot: wanted">⚖</span>` : "")},
  {id: "links", label: "BUILD", cell: (r) => (r.links ? `<a href="${esc(r.links.edsy)}" target="_blank" rel="noopener">EDSY</a> · <a href="${esc(r.links.coriolis)}" target="_blank" rel="noopener">Coriolis</a>` : `<span class="xn-dim" title="Never boarded since your journals begin">—</span>`)},
];
const MODULES = [
  {id: "name", label: "MODULE", cell: (r) => `<b>${esc(r.name)}</b>${r.size ? ` <small>${r.size}${esc(r.rating || "")}${r.mount ? ` ${esc(r.mount)}` : ""}</small>` : ""}`, sort: (r) => r.name},
  {id: "eng", label: "ENGINEERING", cell: (r) => (r.blueprint ? `${esc(r.blueprint)}${r.level ? ` G${r.level}` : ""}` : ""), sort: (r) => r.blueprint, fit: 2},
  {id: "where", label: "WHERE", cell: (r) => (r.in_transit ? "in transit" : esc(r.system || "")), sort: (r) => r.system},
  {id: "value", label: "VALUE", cell: (r) => credits(r.value), sort: (r) => r.value, cls: "xt-num", firstDir: "desc"},
  {id: "move", label: "TO BRING HERE", short: "MOVE", cell: (r) => (r.transfer_cost ? credits(r.transfer_cost) : ""), sort: (r) => r.transfer_cost, cls: "xt-num", fit: 3},
];
const MISSIONS = [
  {id: "name", label: "MISSION", cell: (r) => `<b>${esc(r.name)}</b><div class="xn-dim">${esc(r.faction || "")}</div>`, sort: (r) => r.name},
  {id: "where", label: "WHERE", cell: (r) => esc([r.system, r.station].filter(Boolean).join(" · ")), sort: (r) => r.system},
  {id: "left", label: "TIME LEFT", cell: (r) => (r.expires_in === null || r.expires_in === undefined ? "" : r.expired ? `<span class="xb-high">expired</span>` : `<span class="${r.soon ? "xb-high" : ""}">${hours(r.expires_in)}</span>`), sort: (r) => r.expires_in, cls: "xt-num"},
  {id: "progress", label: "PROGRESS", cell: (r) => (r.massacre ? `${r.kills ?? 0} / ${r.count ?? "?"} kills` : r.count ? `${r.delivered ?? 0} / ${r.count} ${esc(r.commodity || "")}` : esc(r.target || "")), sort: (r) => r.kills},
  {id: "reward", label: "REWARD", cell: (r) => credits(r.reward), sort: (r) => r.reward, cls: "xt-num", firstDir: "desc"},
];
const SESSIONS = [
  {id: "start", label: "LOGIN", cell: (r) => esc(String(r.start || "").replace("T", " ").slice(0, 16)), sort: (r) => r.start, firstDir: "desc"},
  {id: "ship", label: "SHIP", cell: (r) => esc((r.combat?.ships || r.mining?.ships || [r.ship]).filter(Boolean).join(", ")), sort: (r) => r.ship, fit: 3},
  {id: "kills", label: "KILLS", cell: (r) => (r.combat ? `${r.combat.kills}${r.combat.per_hour ? ` <small>${r.combat.per_hour}/h</small>` : ""}` : ""), sort: (r) => r.combat?.kills, cls: "xt-num", firstDir: "desc"},
  {id: "bounties", label: "BOUNTIES", cell: (r) => (r.combat ? credits(r.combat.bounties + r.combat.bonds) : ""), sort: (r) => r.combat?.bounties, cls: "xt-num", fit: 2},
  {id: "by", label: "BY SHIP", cell: (r) => (r.combat ? esc(Object.entries(r.combat.by_ship || {}).slice(0, 4).map(([ship, n]) => `${ship} ${n}`).join(", ")) : ""), fit: 3},
  {id: "deaths", label: "DEATHS", cell: (r) => (r.combat?.deaths || ""), sort: (r) => r.combat?.deaths, cls: "xt-num"},
  {id: "where", label: "MINED AT", cell: (r) => (r.mining ? esc((r.mining.places || []).slice(0, 2).map((p) => p.body || p.system).join(", ")) : ""), fit: 2},
  {id: "tons", label: "TONS", cell: (r) => (r.mining ? `${r.mining.tons + r.mining.srv_tons}${r.mining.per_hour ? ` <small>${r.mining.per_hour} t/h</small>` : ""}` : ""), sort: (r) => r.mining?.tons, cls: "xt-num", firstDir: "desc"},
  {id: "prospected", label: "PROSPECTED", short: "PROSP", cell: (r) => (r.mining?.prospected || ""), sort: (r) => r.mining?.prospected, cls: "xt-num", fit: 3},
  {id: "limpets", label: "LIMPETS", cell: (r) => (r.mining ? `${r.mining.prospectors}+${r.mining.collectors}` : ""), cls: "xt-num", fit: 3},
  {id: "sold", label: "SOLD", cell: (r) => (r.mining?.sold ? credits(r.mining.sold) : ""), sort: (r) => r.mining?.sold, cls: "xt-num"},
];
const HOTSPOTS = [
  {id: "ring", label: "RING", cell: (r) => `<b>${esc(r.ring)}</b>${r.hotspot ? `<div class="xn-dim">${esc(r.hotspot)}</div>` : `<div class="xn-dim">hotspot not known</div>`}`, sort: (r) => r.ring},
  {id: "what", label: "REFINED", cell: (r) => esc(Object.entries(r.refined || {}).slice(0, 3).map(([what, n]) => `${what} ${n}`).join(", ")), fit: 2},
  {id: "stints", label: "STINTS", cell: (r) => r.stints, sort: (r) => r.stints, cls: "xt-num", firstDir: "desc"},
  {id: "tons", label: "TONS", cell: (r) => r.tons, sort: (r) => r.tons, cls: "xt-num", firstDir: "desc"},
  {id: "hit", label: "HIGH %", cell: (r) => (r.hit_rate === null ? "" : `${r.hit_rate}%`), sort: (r) => r.hit_rate, cls: "xt-num", fit: 3},
  {id: "tph", label: "BEST T/H", cell: (r) => r.best_tph ?? "", sort: (r) => r.best_tph, cls: "xt-num", firstDir: "desc"},
  {id: "crh", label: "CR/H", cell: (r) => credits(r.cr_h), sort: (r) => r.cr_h, cls: "xt-num", fit: 2},
  {id: "last", label: "LAST", cell: (r) => esc(String(r.last || "").slice(0, 10)), sort: (r) => r.last, firstDir: "desc"},
];

function goalsMarkup(goals) {
  if (!goals?.length) return `<p class="workspace-empty">You're not signed up to a Community Goal.</p>`;
  return goals.map((g) => `<div class="cmdr-goal"><b>${esc(g.title)}</b><span>${esc([g.system, g.station].filter(Boolean).join(" · "))}</span>
    <small>tier ${esc(g.tier ?? "?")}${g.top_tier ? ` of ${esc(g.top_tier)}` : ""} · your contribution ${credits(g.contribution) || g.contribution || 0} · ${g.band ? `top ${esc(g.band)}` : ""}${g.expires_in ? ` · ${hours(g.expires_in)} left` : ""}</small></div>`).join("");
}

// Where to cash them (5.7.8, after ED-Outrider): each faction's own nearest
// station, and the nearest Interstellar Factors (any voucher, less its cut).
function placeMarkup(place) {
  if (!place) return `<small class="xn-dim">none known</small>`;
  return `<small>${esc(place.name)} · ${esc(place.system)}${place.distance !== null && place.distance !== undefined ? ` · ${Math.round(place.distance).toLocaleString()} ly` : ""}</small>
    <button type="button" class="xc-pic" data-cmdr-copy="${esc(place.system)}" title="Copy the system">⧉</button>`;
}

function vouchersMarkup(v, where) {
  if (!v) return `<p class="workspace-empty">No bounty vouchers or combat bonds held.</p>`;
  const asking = !where || where.status === "working";
  const rows = v.factions.map((f) => `<div><span>${esc(f.name)}<br>${asking ? `<small class="xn-dim">looking…</small>` : placeMarkup(where.factions?.[f.name])}</span><b>${credits(f.total)} cr</b></div>`).join("");
  const factors = asking ? "" : `<div><span>Interstellar Factors<br>${placeMarkup(where.factors)}</span><b class="xn-dim">any, less its cut</b></div>`;
  return `<div class="fact-list spacious">${rows}${factors}</div><p class="xn-note">Lost if you die: cash them in. A faction's own stations take its vouchers at Contacts.</p>`;
}

function earningsMarkup(e) {
  if (!e || e.working || !Array.isArray(e.months)) return `<p class="workspace-empty">Reading your journals…</p>`;
  const max = Math.max(1, ...e.months.map((m) => e.kinds.reduce((sum, kind) => sum + (m[kind] || 0), 0)));
  const bars = e.months.slice(-36).map((m) => {
    const total = e.kinds.reduce((sum, kind) => sum + (m[kind] || 0), 0);
    const stack = e.kinds.map((kind) => (m[kind] ? `<i class="cmdr-k-${kind}" style="height:${(100 * m[kind] / max).toFixed(2)}%" title="${KIND_LABELS[kind]}: ${credits(m[kind])}"></i>` : "")).join("");
    return `<button type="button" class="cmdr-bar" data-cmdr-period="${m.month}" title="${m.month}: ${credits(total)}">${stack}<small>${m.month.slice(2)}</small></button>`;
  }).join("");
  const legend = e.kinds.map((kind) => `<span><i class="cmdr-k-${kind}"></i>${KIND_LABELS[kind]} ${credits(e.totals[kind]) || 0}</span>`).join("");
  const list = (rows) => rows.map((row) => `<div><span>${esc(row.name)}</span><b>${credits(row.amount)}</b></div>`).join("") || "<p class='workspace-empty'>—</p>";
  return `<div class="cmdr-earn-head"><label>PERIOD<select data-cmdr-period-select>${e.periods.map((p) => `<option ${p === e.period ? "selected" : ""}>${p}</option>`).join("")}</select></label>
      <b>${credits(e.total)} cr</b><span>${e.count} sales</span><button type="button" data-cmdr-csv>CSV</button></div>
    <div class="cmdr-chart">${bars || "<p class='workspace-empty'>No earnings in your journals yet.</p>"}</div><div class="cmdr-legend">${legend}</div>
    <div class="workspace-grid three">
      <article class="card workspace-card"><header><span>WHERE YOU SOLD MOST</span></header><div class="fact-list">${list(e.stations)}</div></article>
      <article class="card workspace-card"><header><span>SPECIES THAT PAID MOST</span></header><div class="fact-list">${list(e.species)}</div></article>
      <article class="card workspace-card"><header><span>EACH SHIP'S RECORD</span></header><div class="fact-list">${list(e.ships)}</div></article>
    </div>
    <div class="xt-box cmdr-sales" data-cmdr-sales></div>
    <p class="xn-note">Mining counts only ore you mined yourself; trade counts the profit on what you bought.</p>`;
}

const SALES = [
  {id: "ts", label: "WHEN", cell: (r) => esc(String(r.ts).replace("T", " ").slice(0, 16)), sort: (r) => r.ts, firstDir: "desc"},
  {id: "kind", label: "WHAT", cell: (r) => `<span class="cmdr-k cmdr-kt-${r.kind}">${KIND_LABELS[r.kind]}</span> <small>${esc(r.detail || "")}</small>`, sort: (r) => r.kind},
  {id: "where", label: "WHERE", cell: (r) => esc([r.station, r.system].filter(Boolean).join(" · ")), sort: (r) => r.station, fit: 2},
  {id: "ship", label: "SHIP", cell: (r) => esc(r.ship || ""), sort: (r) => r.ship, fit: 3},
  {id: "amount", label: "CREDITS", cell: (r) => credits(r.amount), sort: (r) => r.amount, cls: "xt-num", firstDir: "desc"},
];

function ensureTabs(root) {
  if (root.querySelector(":scope > .cmdr-tabs")) return;
  const nav = document.createElement("nav");
  nav.className = "co-tabs cmdr-tabs";
  nav.setAttribute("role", "tablist");
  nav.innerHTML = TABS.map(([id, label]) => `<button type="button" role="tab" data-cmdr-tab="${id}">${label}</button>`).join("");
  const anchor = root.querySelector(":scope > .workspace-metrics") || root.firstElementChild;
  anchor?.after(nav);
  const panels = {};
  for (const [id] of TABS) {
    const panel = document.createElement("section");
    panel.className = "cmdr-panel";
    panel.dataset.cmdrPanel = id;
    panel.innerHTML = `<div class="cmdr-book" data-cmdr-book="${id}"></div><div class="workspace-grid two cmdr-cards"></div>`;
    root.append(panel);
    panels[id] = panel;
  }
  for (const card of [...root.querySelectorAll(".profile-workspace-grid > .workspace-card")]) {
    panels[tabOf(card.querySelector("header > span")?.textContent)]?.querySelector(".cmdr-cards").append(card);
  }
  root.querySelector(".profile-workspace-grid")?.remove();
}

function showTab(root) {
  for (const button of root.querySelectorAll("[data-cmdr-tab]")) button.classList.toggle("active", button.dataset.cmdrTab === st.tab);
  for (const panel of root.querySelectorAll("[data-cmdr-panel]")) panel.hidden = panel.dataset.cmdrPanel !== st.tab;
}

function fill(root) {
  const book = st.book;
  const slot = (id) => root.querySelector(`[data-cmdr-book="${id}"]`);
  const working = book?.working ? `<p class="workspace-empty">Reading your journals for the books… (the first time takes a little while)</p>` : "";
  const cmdr = slot("cmdr");
  if (cmdr) cmdr.innerHTML = working || moneyMarkup(book) + ranksMarkup(book);
  const fleet = slot("fleet");
  if (fleet && book && !book.working) {
    if (!fleet.querySelector("[data-cmdr-fleet]")) {
      fleet.innerHTML = `<h4 class="cmdr-h">YOUR WHOLE FLEET</h4><div class="xt-box cmdr-box" data-cmdr-fleet></div><h4 class="cmdr-h">STORED MODULES</h4><div class="xt-box cmdr-box" data-cmdr-modules></div>`;
    }
    renderTable(fleet.querySelector("[data-cmdr-fleet]"), {id: "cmdr-fleet", profile: st.profile, columns: FLEET, rows: book.fleet || [],
      key: (r) => String(r.id), sort: {col: "value", dir: "desc"}, empty: "No ships known yet: open a shipyard in the game."});
    renderTable(fleet.querySelector("[data-cmdr-modules]"), {id: "cmdr-modules", profile: st.profile, columns: MODULES, rows: book.modules || [],
      key: (r) => `${r.name}|${r.system}|${r.value}|${r.blueprint}`, sort: {col: "eng", dir: "asc"}, empty: "No stored modules (or the game hasn't listed them yet: open outfitting)."});
    for (const card of root.querySelectorAll('[data-cmdr-panel="fleet"] .workspace-card')) {
      if (/^STORED FLEET/.test(card.querySelector("header > span")?.textContent || "")) card.hidden = true;
    }
  } else if (fleet) fleet.innerHTML = working;
  const missions = slot("missions");
  if (missions && book && !book.working) {
    if (!missions.querySelector("[data-cmdr-missions]")) {
      missions.innerHTML = `<h4 class="cmdr-h">MISSIONS · SOONEST FIRST</h4><div class="xt-box cmdr-box" data-cmdr-missions></div>
        <div class="workspace-grid two"><article class="card workspace-card"><header><span>COMMUNITY GOALS</span></header><div data-cmdr-goals></div></article>
        <article class="card workspace-card"><header><span>BOUNTIES AND BONDS HELD</span></header><div data-cmdr-vouchers></div></article></div>`;
    }
    renderTable(missions.querySelector("[data-cmdr-missions]"), {id: "cmdr-missions", profile: st.profile, columns: MISSIONS, rows: book.missions || [],
      key: (r) => String(r.id), sort: {col: "left", dir: "asc"}, empty: "No missions in hand."});
    missions.querySelector("[data-cmdr-goals]").innerHTML = goalsMarkup(book.goals);
    missions.querySelector("[data-cmdr-vouchers]").innerHTML = vouchersMarkup(book.vouchers, st.where);
    if (book.vouchers && !st.whereAsked) askWhere(root);
    for (const card of root.querySelectorAll('[data-cmdr-panel="missions"] .workspace-card')) {
      if (/^MISSION RESPONSIBILITIES/.test(card.querySelector("header > span")?.textContent || "")) card.hidden = true;
    }
  } else if (missions) missions.innerHTML = working;
  const sessions = slot("sessions");
  if (sessions && book && !book.working) {
    if (!sessions.querySelector("[data-cmdr-sessions]")) {
      sessions.innerHTML = `<h4 class="cmdr-h">FIGHTING AND MINING, BY LOGIN</h4><div class="xt-box cmdr-box" data-cmdr-sessions></div>
        <h4 class="cmdr-h">HOTSPOTS · EVERY RING YOU'VE MINED</h4><div class="xt-box cmdr-box" data-cmdr-hotspots></div>
        <p class="xn-note">The journal never names a hotspot; Void Compass learns it from the game's destination as you drop in, so older mining shows "hotspot not known".</p>`;
    }
    renderTable(sessions.querySelector("[data-cmdr-sessions]"), {id: "cmdr-sessions", profile: st.profile, columns: SESSIONS, rows: book.sessions || [],
      key: (r) => r.start, sort: {col: "start", dir: "desc"}, empty: "No fighting or mining in your journals."});
    renderTable(sessions.querySelector("[data-cmdr-hotspots]"), {id: "cmdr-hotspots", profile: st.profile, columns: HOTSPOTS, rows: book.hotspots || [],
      key: (r) => r.ring, sort: {col: "last", dir: "desc"}, empty: "No ring mining in your journals."});
  } else if (sessions) sessions.innerHTML = working;
  const earnings = slot("earnings");
  if (earnings) {
    const html = earningsMarkup(st.earnings);
    if (earnings._html !== html) {
      earnings._html = html;
      earnings.innerHTML = html;
    }
    const box = earnings.querySelector("[data-cmdr-sales]");
    if (box && st.earnings) renderTable(box, {id: "cmdr-sales", profile: st.profile, columns: SALES, rows: st.earnings.sales || [],
      key: (r) => `${r.ts}|${r.kind}|${r.amount}`, sort: {col: "ts", dir: "desc"}});
  }
}

async function askWhere(root) {
  st.whereAsked = true;
  try {
    st.where = await fetchData(st.ui, "cmdr-vouchers");
  } catch (_error) {
    st.where = {status: "failed", factions: {}, factors: null};
  }
  const box = document.querySelector("[data-cmdr-vouchers]");
  if (box && st.book?.vouchers) box.innerHTML = vouchersMarkup(st.book.vouchers, st.where);
  if (st.where?.status === "working") setTimeout(() => askWhere(root), 2500);
}

async function load(root) {
  if (st.loading) return;
  st.loading = true;
  try {
    st.book = await fetchData(st.ui, "cmdr-book");
    st.whereAsked = false;
    if (!st.book.working) st.earnings = await fetchData(st.ui, "cmdr-earnings", {period: st.period});
    st.lastFetch = Date.now();
  } catch (_error) { /* asked again */ } finally {
    st.loading = false;
  }
  const live = document.getElementById("profile-workspace");
  if (live) fill(live);
  clearTimeout(st.polling);
  if (st.book?.working) st.polling = setTimeout(() => load(root), 2000);
}

function bind(root) {
  if (root.dataset.cmdrBound) return;
  root.dataset.cmdrBound = "1";
  root.addEventListener("click", async (event) => {
    const copy = event.target.closest("[data-cmdr-copy]");
    if (copy) {
      if (await st.ui?.command?.("workspace", {page: "explore", operation: "copy_system", name: copy.dataset.cmdrCopy})) st.ui?.showToast?.(`${copy.dataset.cmdrCopy} copied`);
      return;
    }
    const tab = event.target.closest("[data-cmdr-tab]");
    if (tab) {
      st.tab = tab.dataset.cmdrTab;
      try { localStorage.setItem(`voidcompass.cmdr.tab.${st.profile}`, st.tab); } catch (_error) { /* convenience */ }
      showTab(root);
      return;
    }
    const bar = event.target.closest("[data-cmdr-period]");
    if (bar) {
      st.period = bar.dataset.cmdrPeriod;
      fetchData(st.ui, "cmdr-earnings", {period: st.period}).then((data) => { st.earnings = data; fill(root); }).catch(() => {});
      return;
    }
    if (event.target.closest("[data-cmdr-csv]") && st.earnings) {
      downloadText(`earnings-${st.earnings.period}.csv`, toCsv(["Time", "Kind", "Detail", "Station", "System", "Ship", "Credits"],
        (st.earnings.sales || []).map((r) => [r.ts, KIND_LABELS[r.kind], r.detail, r.station, r.system, r.ship, r.amount])));
    }
  });
  root.addEventListener("change", (event) => {
    if (!event.target.matches("[data-cmdr-period-select]")) return;
    st.period = event.target.value;
    fetchData(st.ui, "cmdr-earnings", {period: st.period}).then((data) => { st.earnings = data; fill(root); }).catch(() => {});
  });
}

/** After the record is drawn: its cards into tabs, and the books filled in. */
export function renderCmdr(root, ui, profile) {
  if (!root) return;
  st.ui = ui;
  if (st.profile !== profile) {
    st.profile = profile;
    st.book = null;
    st.earnings = null;
    try { st.tab = localStorage.getItem(`voidcompass.cmdr.tab.${profile}`) || "cmdr"; } catch (_error) { st.tab = "cmdr"; }
  }
  bind(root);
  ensureTabs(root);
  showTab(root);
  fill(root);
  if (!st.book || Date.now() - st.lastFetch > 30000) load(root);
}
