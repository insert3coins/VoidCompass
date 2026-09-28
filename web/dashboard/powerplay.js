/* Powerplay Operations: the pledge, the weekly cycle clock, the system you
   are in, every Powerplay system you have jumped through, and the ledgers.
   Every number comes from the journal; assignments are the commander's own.
   Tabs, the intel filter and "assign" prefills stay in the page: only the
   data-ws-op buttons reach the backend. */

const PORTRAITS = "images/people/powerplay/";
const TABS = [["ops", "OPERATIONS"], ["intel", "SYSTEM INTEL"], ["ledgers", "LEDGERS"], ["powers", "POWERS"]];
const RELATIONS = {
  ours: ["OURS", "Held by your power"],
  hostile: ["HOSTILE", "Held by a rival power"],
  acquisition: ["ACQUISITION", "Your power can take this system"],
  out_of_reach: ["OUT OF REACH", "Your power has no foothold here"],
  unaligned: ["OBSERVED", "Pledge to a power to see where you stand"],
  none: ["NO POWERPLAY", "No power reported in this system"],
};
const INTEL_FILTERS = [["all", "ALL"], ["ours", "OURS"], ["hostile", "HOSTILE"], ["acquisition", "ACQUISITION"], ["out_of_reach", "OUT OF REACH"]];
const TIERS = ["EXPLOITED", "FORTIFIED", "STRONGHOLD"];
const ACTION_NOTES = {
  REINFORCE: "Hold the line: work here reinforces it against undermining.",
  UNDERMINE: "Break their grip: work here undermines the controlling power.",
  ACQUIRE: "Take it: work here pushes your power's conflict progress.",
};
const KIND_ICONS = {general: "◆", system: "⌖", cargo: "▣", collect: "▲", deliver: "▼"};
const DAY = 86400000;

const memory = {tab: "ops", filter: "all", search: ""};
try { memory.tab = window.localStorage.getItem("voidcompass.powerplay.tab") || "ops"; } catch { /* storage may be blocked */ }
let ticker = 0;

const finite = (value) => value !== null && value !== undefined && value !== "" && Number.isFinite(Number(value));
const clamp = (value, low, high) => Math.max(low, Math.min(high, value));

function countdown(value) {
  const end = Date.parse(value || "");
  if (!Number.isFinite(end)) return "—";
  const seconds = Math.max(0, Math.floor((end - Date.now()) / 1000));
  const pad = (number) => String(number).padStart(2, "0");
  return `${Math.floor(seconds / 86400)}D ${pad(Math.floor(seconds % 86400 / 3600))}:${pad(Math.floor(seconds % 3600 / 60))}:${pad(seconds % 60)}`;
}

function ago(value) {
  const then = Date.parse(value || "");
  if (!Number.isFinite(then)) return "—";
  const minutes = Math.max(0, Math.floor((Date.now() - then) / 60000));
  if (minutes < 1) return "JUST NOW";
  if (minutes < 60) return `${minutes} MIN AGO`;
  if (minutes < 1440) return `${Math.floor(minutes / 60)} H AGO`;
  return `${Math.floor(minutes / 1440)} D AGO`;
}

function when(value) {
  const parsed = Date.parse(value || "");
  return Number.isFinite(parsed) ? new Date(parsed).toLocaleString([], {day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit"}) : "—";
}

function dayLabel(value) {
  const parsed = Date.parse(`${value || ""}T12:00:00Z`);
  return Number.isFinite(parsed) ? new Date(parsed).toLocaleDateString([], {day: "2-digit", month: "short"}).toUpperCase() : "—";
}

function pledgedFor(seconds) {
  if (!finite(seconds)) return "—";
  const total = Math.max(0, Number(seconds));
  const days = Math.floor(total / 86400);
  return days ? `${days.toLocaleString()}D ${Math.floor(total % 86400 / 3600)}H` : `${Math.floor(total / 3600)}H ${Math.floor(total % 3600 / 60)}M`;
}

// The clock, the week bar, today's column and every "ago" label move every
// second without re-rendering the page.
function tick() {
  const root = document.getElementById("powerplay-workspace");
  if (!root || !root.offsetParent) return;
  root.querySelectorAll("[data-pp-countdown]").forEach((node) => { node.textContent = countdown(node.dataset.ppCountdown); });
  root.querySelectorAll("[data-pp-ago]").forEach((node) => { node.textContent = ago(node.dataset.ppAgo); });
  root.querySelectorAll("[data-pp-week]").forEach((node) => {
    const start = Date.parse(node.dataset.start || ""), end = Date.parse(node.dataset.end || "");
    if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) return;
    const elapsed = clamp((Date.now() - start) / (end - start), 0, 1);
    node.style.setProperty("--elapsed", `${(elapsed * 100).toFixed(3)}%`);
    const today = Math.floor((Date.now() - start) / DAY);
    node.querySelectorAll("[data-day]").forEach((day) => {
      const index = Number(day.dataset.day);
      day.classList.toggle("today", index === today);
      day.classList.toggle("future", index > today);
    });
  });
}

function bind(root) {
  if (root.dataset.ppBound) return;
  root.dataset.ppBound = "1";
  root.addEventListener("click", (event) => {
    const tabButton = event.target.closest("[data-pp-tab]");
    if (tabButton) {
      memory.tab = tabButton.dataset.ppTab;
      try { window.localStorage.setItem("voidcompass.powerplay.tab", memory.tab); } catch { /* storage may be blocked */ }
      applyTab(root);
      return;
    }
    const filterButton = event.target.closest("[data-pp-filter]");
    if (filterButton) {
      memory.filter = filterButton.dataset.ppFilter;
      applyIntelFilter(root);
      return;
    }
    const assign = event.target.closest("[data-pp-assign]");
    if (assign) prefillAssignment(root, assign.dataset.ppAssign, assign.dataset.ppSystem || "");
  });
  root.addEventListener("input", (event) => {
    if (event.target.id === "pp-intel-search") {
      memory.search = event.target.value;
      applyIntelFilter(root);
    } else if (event.target.closest("#powerplay-assignment-form")) {
      event.target.dataset.dirty = "1";
    }
  });
  root.addEventListener("submit", (event) => event.preventDefault());
}

function applyTab(root) {
  if (!TABS.some(([key]) => key === memory.tab)) memory.tab = "ops";
  root.querySelectorAll("[data-pp-tab]").forEach((node) => {
    const active = node.dataset.ppTab === memory.tab;
    node.classList.toggle("active", active);
    node.setAttribute("aria-selected", String(active));
  });
  root.querySelectorAll("[data-pp-panel]").forEach((node) => { node.hidden = node.dataset.ppPanel !== memory.tab; });
}

function applyIntelFilter(root) {
  const search = memory.search.trim().toLowerCase();
  let shown = 0;
  root.querySelectorAll("[data-pp-filter]").forEach((node) => node.classList.toggle("active", node.dataset.ppFilter === memory.filter));
  root.querySelectorAll(".pp-intel-row").forEach((row) => {
    const visible = (memory.filter === "all" || row.dataset.relation === memory.filter)
      && (!search || row.dataset.search.includes(search));
    row.hidden = !visible;
    shown += Number(visible);
  });
  const none = root.querySelector(".pp-intel-none");
  if (none) none.hidden = shown > 0 || !root.querySelector(".pp-intel-row");
}

function prefillAssignment(root, action, system) {
  memory.tab = "ops";
  applyTab(root);
  const words = {REINFORCE: "Reinforce", UNDERMINE: "Undermine", ACQUIRE: "Acquire"};
  const fields = {
    "powerplay-objective-title": `${words[action] || "Work"} ${system}`.trim(),
    "powerplay-objective-kind": "system",
    "powerplay-objective-system": system,
  };
  for (const [id, value] of Object.entries(fields)) {
    const input = root.querySelector(`#${id}`);
    if (input) { input.value = value; input.dataset.dirty = "1"; }
  }
  const title = root.querySelector("#powerplay-objective-title");
  title?.scrollIntoView({block: "center", behavior: "smooth"});
  title?.focus();
}

// A journal publish re-renders the page; keep whatever the commander was
// typing into the assignment form (untouched fields follow the journal).
function keepDrafts(root) {
  return [...root.querySelectorAll("#powerplay-assignment-form [data-dirty]")].map((node) => [node.id, node.value]);
}

function restoreDrafts(root, drafts) {
  for (const [id, value] of drafts) {
    const node = root.querySelector(`#${id}`);
    if (node) { node.value = value; node.dataset.dirty = "1"; }
  }
}

function portrait(file, h, className = "") {
  return file ? `<img class="${className}" src="${PORTRAITS}${h.esc(file)}" alt="" loading="lazy" onerror="this.hidden=true">` : "";
}

function relationBadge(relation) {
  const [label, hint] = RELATIONS[relation] || RELATIONS.none;
  return `<span class="pp-relation rel-${relation || "none"}" title="${hint}">${label}</span>`;
}

function tierPips(tier) {
  return `<i class="pp-pips" aria-label="Tier ${tier} of 3">${[1, 2, 3].map((step) => `<b class="${step <= tier ? "on" : ""}"></b>`).join("")}</i>`;
}

function controlBar(value, delta, h, compact = false) {
  if (!finite(value)) return compact ? `<span class="pp-muted">—</span>` : "";
  const percent = Number(value) * 100;
  const change = finite(delta) && Math.abs(Number(delta)) >= 0.0005
    ? `<em class="${Number(delta) >= 0 ? "up" : "down"}" title="Change since the last different reading this cycle">${Number(delta) >= 0 ? "▲" : "▼"} ${Math.abs(Number(delta) * 100).toFixed(1)}%</em>` : "";
  return `<div class="pp-control${compact ? " compact" : ""}">${compact ? "" : "<span>CONTROL PROGRESS</span>"}<i><b style="width:${clamp(percent, 0, 100).toFixed(2)}%"></b></i><strong>${h.numeric(percent, 1)}%</strong>${change}</div>`;
}

function tug(reinforcement, undermining, h, compact = false) {
  if (!finite(reinforcement) && !finite(undermining)) return compact ? `<span class="pp-muted">—</span>` : "";
  const held = Math.max(0, Number(reinforcement) || 0), lost = Math.max(0, Number(undermining) || 0);
  const share = held + lost ? held * 100 / (held + lost) : 50;
  if (compact) {
    return `<div class="pp-tug compact${held + lost ? "" : " idle"}" title="Reinforcement ${h.numeric(held)} · Undermining ${h.numeric(lost)}"><b>${h.numeric(held)}</b><i><em style="width:${share.toFixed(2)}%"></em></i><b>${h.numeric(lost)}</b></div>`;
  }
  return `<div class="pp-tug${held + lost ? "" : " idle"}"><div><span>REINFORCEMENT</span><b>${h.numeric(held)}</b></div><i><em style="width:${share.toFixed(2)}%"></em></i><div><span>UNDERMINING</span><b>${h.numeric(lost)}</b></div></div>`;
}

// An acquisition fight has no control bar: show your power's share of it (or
// the leader's, when yours isn't in it) and who is ahead.
function conflictBar(row, power, h) {
  const rows = row.conflict || [];
  if (!rows.length) return "";
  const leader = rows[0];
  const mine = rows.find((entry) => entry.power === power);
  const shown = mine || leader;
  const note = mine ? (mine === leader ? "YOU LEAD" : `${leader.power} LEADS`) : `${leader.power} LEADS`;
  const title = rows.map((entry) => `${entry.power} ${h.numeric(Number(entry.progress) * 100, 1)}%`).join(" · ");
  return `<div class="pp-control compact conflict" title="Conflict progress: ${h.esc(title)}"><i><b style="width:${clamp(Number(shown.progress) * 100, 0, 100).toFixed(2)}%"></b></i><strong>${h.numeric(Number(shown.progress) * 100, 1)}%</strong><em class="${mine ? (mine === leader ? "up" : "down") : "note"}">${h.esc(String(note).toUpperCase())}</em></div>`;
}

/* The hero: who you fly for, your rank and the clock to the weekly tick. */
function renderHero(data, h) {
  const power = data.powerplay || {};
  const pledged = data.pledged_dossier || {};
  const cycle = data.cycle || {};
  const rank = data.rank || {};
  const isPledged = Boolean(power.pledged && power.power);
  const face = isPledged && pledged.portrait
    ? portrait(pledged.portrait, h)
    : `<span class="pp-sigil">⚑</span>`;
  const stats = [
    ["TOTAL MERITS", finite(power.merits) ? h.numeric(power.merits) : "—"],
    ["THIS CYCLE", h.numeric(cycle.merits_gained || 0)],
    ["THIS SESSION", `+${h.numeric(data.session_merits || 0)}`],
    ["LAST SALARY", finite(power.salary) ? h.credits(power.salary) : "—"],
    ["PLEDGED FOR", pledgedFor(power.time_pledged)],
  ].map(([label, value]) => `<div><span>${label}</span><b>${value}</b></div>`).join("");
  let rankBlock;
  if (!isPledged) {
    rankBlock = `<div class="pp-rank empty"><div class="pp-hex"><b>—</b></div><p>NO RANK<br><small>Pledge to earn merits and ranks</small></p></div>`;
  } else if (!finite(power.rank)) {
    rankBlock = `<div class="pp-rank empty"><div class="pp-hex"><b>?</b></div><p>RANK PENDING<br><small>The journal reports it at login</small></p></div>`;
  } else {
    const bar = rank.consistent
      ? `<i class="pp-rank-bar"><b style="width:${(Number(rank.fraction) * 100).toFixed(2)}%"></b></i><small><strong>${h.numeric(rank.to_go)}</strong> MERITS TO RANK ${h.numeric(rank.next_rank)}</small>`
      : `<small>Journal rank. The merit total sits outside this rank's band, so no progress bar.</small>`;
    rankBlock = `<div class="pp-rank"><div class="pp-hex"><span>RANK</span><b>${h.numeric(power.rank)}</b></div><div class="pp-rank-next">${bar}${rank.consistent ? `<span>${h.numeric(rank.floor)} → ${h.numeric(rank.next)}</span>` : ""}</div></div>`;
  }
  const days = ["THU", "FRI", "SAT", "SUN", "MON", "TUE", "WED"].map((label, index) => `<span data-day="${index}">${label}</span>`).join("");
  const identity = isPledged
    ? `<small>POWERPLAY 2.0 · PLEDGED COMMANDER</small><h2>${h.esc(power.power)}</h2><p>${h.esc([pledged.allegiance, pledged.headquarters ? `HQ ${pledged.headquarters}` : "", pledged.role].filter(Boolean).join(" · ") || "Galactic power")}</p>`
    : `<small>POWERPLAY 2.0 · NO PLEDGE ON RECORD</small><h2>Unaligned</h2><p>Pledge at any Power Contact and the journal fills this in. The dossiers are under POWERS.</p>`;
  return `<section class="pp-hero${isPledged ? " pledged" : ""}">
    <div class="pp-hero-face">${face}</div>
    <div class="pp-hero-id">${identity}<div class="pp-hero-stats">${stats}</div></div>
    ${rankBlock}
    <div class="pp-clock"><small>CYCLE OF ${dayLabel(cycle.id)} · TICK THU 07:00 UTC</small><b data-pp-countdown="${h.esc(cycle.ends || "")}">${countdown(cycle.ends)}</b><span>UNTIL THE WEEKLY TICK</span>
      <div class="pp-week" data-pp-week data-start="${h.esc(cycle.started || "")}" data-end="${h.esc(cycle.ends || "")}"><i></i>${days}</div></div>
    <footer>${power.last_updated ? `LAST POWERPLAY SIGNAL · <span data-pp-ago="${h.esc(power.last_updated)}">${ago(power.last_updated)}</span>` : "AWAITING POWERPLAY JOURNAL EVENTS"}</footer>
  </section>`;
}

/* OPERATIONS: this system, this cycle, and the assignment board. */
function renderSystem(loc, h) {
  if (!loc.system) {
    return `<article class="pp-card pp-system rel-none"><header><span>THIS SYSTEM</span></header><p class="pp-empty">Jump, or log in, and the journal reports this system's Powerplay state here.</p></article>`;
  }
  const relation = loc.relation || "none";
  const copy = `<button class="pp-ghost ghost" data-ws-page="powerplay" data-ws-op="copy_system" data-system="${h.esc(loc.system)}" title="Copy system name">COPY</button>`;
  const stale = loc.stale ? `<span class="pp-stale" title="Read before the last weekly tick; the state will have moved">PRE-TICK</span>` : "";
  const head = `<header><span>THIS SYSTEM</span>${relationBadge(relation)}${stale}<em data-pp-ago="${h.esc(loc.updated || "")}">${ago(loc.updated)}</em></header>
    <div class="pp-system-name"><h3>${h.esc(loc.system)}</h3>${copy}</div>`;
  if (relation === "none") {
    return `<article class="pp-card pp-system rel-none">${head}<p class="pp-empty">No power holds or contests this system. Powerplay systems you jump through are logged under SYSTEM INTEL.</p></article>`;
  }
  const tier = Number(loc.tier) || 0;
  const firstStep = tier ? "UNOCCUPIED" : String(loc.state || "UNCLAIMED").toUpperCase();
  const ladder = [firstStep, ...TIERS].map((label, index) => `<span class="${index === tier ? "on" : index < tier ? "past" : ""}">${h.esc(label)}</span>`).join("");
  const controller = loc.controlling_power
    ? `<div class="pp-controller">${portrait(loc.controller_portrait, h)}<div><span>CONTROLLED BY</span><b>${h.esc(loc.controlling_power)}</b></div></div>`
    : `<div class="pp-controller none"><span class="pp-sigil small">◇</span><div><span>CONTROL</span><b>UNCONTROLLED</b></div></div>`;
  const conflict = (loc.conflict || []).length
    ? `<div class="pp-conflict"><span>CONFLICT PROGRESS</span>${loc.conflict.map((row) => `<div><b>${h.esc(row.power)}</b><i><em style="width:${clamp(Number(row.progress) * 100, 0, 100).toFixed(2)}%"></em></i><strong>${h.numeric(Number(row.progress) * 100, 1)}%</strong></div>`).join("")}</div>` : "";
  const fighting = new Set((loc.conflict || []).map((row) => row.power));
  const others = (loc.powers || []).filter((name) => name !== loc.controlling_power && !fighting.has(name));
  const present = others.length ? `<div class="pp-present"><span>ALSO PRESENT</span>${others.map((name) => `<b>${h.esc(name)}</b>`).join("")}</div>` : "";
  const orders = loc.action
    ? `<div class="pp-orders act-${loc.action.toLowerCase()}"><small>YOUR ORDERS HERE</small><b>${loc.action}</b><p>${ACTION_NOTES[loc.action] || ""}</p>${loc.ethos ? `<span>ETHOS BONUS · ${h.esc(String(loc.ethos).toUpperCase())}</span>` : ""}<button class="pp-ghost ghost" data-pp-assign="${loc.action}" data-pp-system="${h.esc(loc.system)}">＋ ASSIGNMENT</button></div>`
    : `<div class="pp-orders"><small>YOUR ORDERS HERE</small><b>${RELATIONS[relation]?.[0] || "—"}</b><p>${RELATIONS[relation]?.[1] || ""}.</p></div>`;
  return `<article class="pp-card pp-system rel-${relation}">${head}
    <div class="pp-ladder" aria-label="Powerplay state">${ladder}</div>
    <div class="pp-system-body"><div class="pp-system-facts">${controller}${controlBar(loc.control_progress, loc.progress_delta, h)}${tug(loc.reinforcement, loc.undermining, h)}${conflict}${present}</div>${orders}</div>
    <footer><span>MERITS EARNED HERE THIS CYCLE</span><b>${h.numeric(loc.merits_here || 0)}</b><span class="pp-source">STATE ${h.esc(String(loc.state || "—").toUpperCase())} · AS REPORTED ON ARRIVAL</span></footer>
  </article>`;
}

function renderPulse(data, h) {
  const cycle = data.cycle || {};
  const days = data.cycle_days || [];
  const compare = data.cycle_compare || {};
  const peak = Math.max(1, ...days.map((day) => Number(day.merits) || 0));
  const bars = days.map((day, index) => {
    const value = Number(day.merits) || 0;
    return `<div data-day="${index}" title="${h.esc(day.date)} · ${h.numeric(value)} merits"><em>${value ? h.numeric(value) : ""}</em><i><b style="height:${(value * 100 / peak).toFixed(2)}%"></b></i><span>${day.label}</span></div>`;
  }).join("");
  const gained = Number(cycle.merits_gained) || 0;
  const versus = finite(compare.last)
    ? `${gained >= compare.last ? "▲" : "▼"} ${h.numeric(Math.abs(gained - compare.last))} ${gained >= compare.last ? "AHEAD OF" : "BEHIND"} LAST CYCLE'S TOTAL`
    : "FIRST CYCLE ON RECORD";
  const systems = (cycle.system_rows || []).slice(0, 5);
  const top = Math.max(1, ...systems.map((row) => Number(row.merits) || 0));
  const systemRows = systems.length
    ? systems.map((row) => `<div><b>${h.esc(row.system)}</b><i><em style="width:${(Number(row.merits) * 100 / top).toFixed(2)}%"></em></i><strong>${h.numeric(row.merits)}</strong></div>`).join("")
    : `<p class="pp-empty">Systems where you earn merits this cycle rank here.</p>`;
  const stats = [
    ["SESSION", `+${h.numeric(data.session_merits || 0)}`],
    ["LAST CYCLE", finite(compare.last) ? h.numeric(compare.last) : "—"],
    ["BEST CYCLE", finite(compare.best) ? h.numeric(compare.best) : "—"],
    ["CARGO IN", h.numeric(cycle.cargo_collected || 0)],
    ["CARGO OUT", h.numeric(cycle.cargo_delivered || 0)],
  ].map(([label, value]) => `<div><span>${label}</span><b>${value}</b></div>`).join("");
  return `<article class="pp-card pp-pulse"><header><span>CYCLE PULSE</span><em>CYCLE OF ${dayLabel(cycle.id)}</em></header>
    <div class="pp-pulse-total"><b>${h.numeric(gained)}</b><span>MERITS THIS CYCLE</span><small>${versus}</small></div>
    <div class="pp-days" data-pp-week data-start="${h.esc(cycle.started || "")}" data-end="${h.esc(cycle.ends || "")}">${bars}</div>
    <div class="pp-pulse-stats">${stats}</div>
    <div class="pp-top-systems"><span>TOP SYSTEMS THIS CYCLE</span>${systemRows}</div>
  </article>`;
}

function renderAssignments(data, h) {
  const objectives = data.objectives || [];
  const active = data.active_objective || {};
  const location = data.location || {};
  const cards = objectives.map((row) => {
    const target = Math.max(1, Number(row.target) || 1), current = clamp(Number(row.current) || 0, 0, target);
    const progress = current * 100 / target;
    const kind = String(row.kind || "general");
    const steps = (target >= 50 ? [-10, -1, 1, 10] : [-1, 1]).map((step) =>
      `<button data-ws-page="powerplay" data-ws-op="step_objective" data-objective-id="${h.esc(row.id)}" data-offset="${step}" title="${step > 0 ? "Add" : "Remove"} ${Math.abs(step)}" ${row.complete && step > 0 ? "disabled" : ""}>${step > 0 ? "+" : "−"}${Math.abs(step) === 1 ? "" : Math.abs(step)}</button>`).join("");
    const onOverlay = row.id === active.id && !row.complete;
    return `<article class="pp-task kind-${h.esc(kind)}${row.complete ? " complete" : ""}${onOverlay ? " selected" : ""}">
      <button class="pp-task-main" data-ws-page="powerplay" data-ws-op="select_objective" data-objective-id="${h.esc(row.id)}" title="Show this assignment on the Powerplay overlay">
        <i>${KIND_ICONS[kind] || "◆"}</i><span><small>${h.esc(kind.toUpperCase())}${onOverlay ? " · ON OVERLAY" : ""}${row.complete ? " · COMPLETE" : ""}</small><b>${h.esc(row.title)}</b><em>${h.esc([row.commodity, row.system].filter(Boolean).join(" · ") || "Commander objective")}</em></span></button>
      <div class="pp-task-progress"><i><b style="width:${progress.toFixed(2)}%"></b></i><strong>${h.numeric(current)} / ${h.numeric(target)}</strong></div>
      ${row.notes ? `<p>${h.esc(row.notes)}</p>` : ""}
      <footer><div class="pp-steps">${steps}</div><button data-ws-page="powerplay" data-ws-op="toggle_objective" data-objective-id="${h.esc(row.id)}">${row.complete ? "REOPEN" : "COMPLETE"}</button><button class="danger-action" data-ws-page="powerplay" data-ws-op="delete_objective" data-objective-id="${h.esc(row.id)}">DELETE</button></footer>
    </article>`;
  }).join("");
  const open = objectives.filter((row) => !row.complete).length;
  return `<article class="pp-card pp-assignments"><header><span>ASSIGNMENTS</span><em>${open} ACTIVE · CARGO ASSIGNMENTS COUNT THEMSELVES FROM THE JOURNAL</em></header>
    <form class="pp-assign-form" id="powerplay-assignment-form">
      <label class="wide">ASSIGNMENT<input id="powerplay-objective-title" maxlength="160" placeholder="Reinforce the home front"></label>
      <label>TYPE<select id="powerplay-objective-kind"><option value="general">GENERAL</option><option value="system">SYSTEM</option><option value="collect">COLLECT CARGO</option><option value="deliver">DELIVER CARGO</option></select></label>
      <label>SYSTEM<input id="powerplay-objective-system" maxlength="140" value="${h.esc(location.system || "")}" placeholder="Any system"></label>
      <label>COMMODITY<input id="powerplay-objective-commodity" maxlength="160" placeholder="Any cargo"></label>
      <label class="narrow">TARGET<input id="powerplay-objective-target" type="number" min="1" max="1000000" value="1"></label>
      <label class="wide">NOTES<input id="powerplay-objective-notes" maxlength="500" placeholder="Optional"></label>
      <button class="primary" data-ws-page="powerplay" data-ws-op="add_objective">ADD</button>
    </form>
    <div class="pp-task-grid">${cards || `<p class="pp-empty">No assignments yet. Add one above, or press ＋ ASSIGNMENT on any system.</p>`}</div>
  </article>`;
}

/* SYSTEM INTEL: every Powerplay system the journal has shown you. */
function renderIntel(data, h) {
  const rows = data.intel || [];
  const power = (data.powerplay || {}).pledged ? (data.powerplay || {}).power : "";
  const counts = data.intel_counts || {};
  const filters = INTEL_FILTERS.map(([key, label]) => {
    const count = key === "all" ? rows.length : Number(counts[key]) || 0;
    return `<button type="button" data-pp-filter="${key}" class="rel-${key}">${label}<b>${count}</b></button>`;
  }).join("");
  const body = rows.map((row) => {
    const search = [row.system, row.controlling_power, row.state, ...(row.powers || [])].join(" ").toLowerCase();
    const controller = row.controlling_power
      ? `${portrait(row.controller_portrait, h)}<span><b>${h.esc(row.controlling_power)}</b><small>${(row.powers || []).length > 1 ? `+${row.powers.length - 1} PRESENT` : "SOLE POWER"}</small></span>`
      : `<span class="pp-sigil small">◇</span><span><b>UNCONTROLLED</b><small>${(row.powers || []).length ? `${row.powers.length} CONTESTING` : "NO CLAIMS"}</small></span>`;
    const action = row.action ? `<button class="pp-ghost ghost" data-pp-assign="${row.action}" data-pp-system="${h.esc(row.system)}" title="${row.action.toLowerCase()} ${h.esc(row.system)}: new assignment">＋</button>` : "";
    return `<div class="pp-intel-row rel-${row.relation}${row.stale ? " stale" : ""}" data-relation="${row.relation}" data-search="${h.esc(search)}">
      <div class="pp-intel-system"><b>${h.esc(row.system)}</b><small>${relationBadge(row.relation)}${row.stale ? `<span class="pp-stale" title="Seen before the last weekly tick; the state will have moved">PRE-TICK</span>` : ""}${Number(row.visits) > 1 ? `${h.numeric(row.visits)} VISITS` : "1 VISIT"}</small></div>
      <div class="pp-intel-state"><b>${h.esc(String(row.state || "—").toUpperCase())}</b>${tierPips(Number(row.tier) || 0)}</div>
      <div class="pp-intel-controller">${controller}</div>
      ${finite(row.control_progress) || !(row.conflict || []).length ? controlBar(row.control_progress, row.progress_delta, h, true) : conflictBar(row, power, h)}
      ${tug(row.reinforcement, row.undermining, h, true)}
      <div class="pp-intel-merits"><b>${row.merits_here ? h.numeric(row.merits_here) : "—"}</b><small>MERITS</small></div>
      <div class="pp-intel-seen" data-pp-ago="${h.esc(row.updated || "")}">${ago(row.updated)}</div>
      <div class="pp-intel-actions"><button class="pp-ghost ghost" data-ws-page="powerplay" data-ws-op="copy_system" data-system="${h.esc(row.system)}" title="Copy system name">COPY</button>${action}</div>
    </div>`;
  }).join("");
  return `<article class="pp-card pp-intel"><header><span>SYSTEM INTEL</span><em>${rows.length} SYSTEMS LOGGED · ${h.numeric(counts.stale || 0)} FROM EARLIER CYCLES</em></header>
    <div class="pp-intel-tools"><div class="pp-filters">${filters}</div><input id="pp-intel-search" type="search" placeholder="FIND A SYSTEM OR POWER…" value="${h.esc(memory.search)}" autocomplete="off"></div>
    ${rows.length ? `<div class="pp-intel-head"><span>SYSTEM</span><span>STATE</span><span>CONTROL</span><span>PROGRESS</span><span>REINFORCED · UNDERMINED</span><span>YOURS</span><span>SEEN</span><span></span></div><div class="pp-intel-list">${body}</div><p class="pp-empty pp-intel-none" hidden>No logged system matches this filter.</p>`
      : `<p class="pp-empty">Every Powerplay system you jump into is logged here with its state, controlling power, control progress and reinforcement against undermining, and the change since your last visit.</p>`}
  </article>`;
}

/* LEDGERS: merits over time, cargo, and the cycle archive. */
function meritChart(series, h) {
  if (series.length < 2) return `<p class="pp-empty">The timeline draws once the journal has reported your merit total twice.</p>`;
  const width = 1000, height = 220;
  const times = series.map((row) => Date.parse(row.timestamp));
  const first = Math.min(...times), last = Math.max(...times, first + 1);
  const totals = series.map((row) => Number(row.total) || 0);
  const low = Math.min(...totals), high = Math.max(...totals, low + 1);
  const peakDelta = Math.max(1, ...series.map((row) => Number(row.delta) || 0));
  const x = (time) => ((time - first) / (last - first)) * width;
  const y = (value) => 10 + (1 - (value - low) / (high - low)) * 140;
  let line = `M${x(times[0]).toFixed(1)},${y(totals[0]).toFixed(1)}`;
  for (let index = 1; index < series.length; index += 1) line += `H${x(times[index]).toFixed(1)}V${y(totals[index]).toFixed(1)}`;
  const area = `${line}H${width}V150H0Z`;
  const barWidth = Math.max(2, Math.min(14, width / series.length * .6));
  const bars = series.map((row, index) => {
    const value = Number(row.delta) || 0;
    if (!value) return "";
    const size = value / peakDelta * 52;
    return `<rect x="${(x(times[index]) - barWidth / 2).toFixed(1)}" y="${(height - size).toFixed(1)}" width="${barWidth.toFixed(1)}" height="${size.toFixed(1)}"><title>+${h.numeric(value)} · ${when(row.timestamp)}</title></rect>`;
  }).join("");
  return `<div class="pp-chart"><svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-label="Total merits over time">
      <path class="area" d="${area}"/><path class="line" d="${line}"/><line class="base" x1="0" x2="${width}" y1="${height - 58}" y2="${height - 58}"/><g class="bars">${bars}</g></svg>
    <span class="hi">${h.numeric(high)}</span><span class="lo">${h.numeric(low)}</span><span class="gain">GAINS</span>
    <span class="from">${when(series[0].timestamp)}</span><span class="to">${when(series[series.length - 1].timestamp)}</span></div>`;
}

function renderLedgers(data, h) {
  const series = data.merit_series || [];
  const cycle = data.cycle || {};
  const history = [...(data.cycle_history || [])].reverse();
  const columns = [...history.map((row) => ({...row, current: false})), {...cycle, current: true}];
  const best = Math.max(1, ...columns.map((row) => Number(row.merits_gained) || 0));
  const archive = columns.map((row) => {
    const value = Number(row.merits_gained) || 0;
    return `<div class="${row.current ? "current" : ""}${value === best && value ? " best" : ""}" title="${h.esc(row.power || "")} · ${h.numeric(row.cargo_collected || 0)} collected · ${h.numeric(row.cargo_delivered || 0)} delivered"><em>${h.numeric(value)}</em><i><b style="height:${(value * 100 / best).toFixed(2)}%"></b></i><span>${row.current ? "NOW" : dayLabel(row.id)}</span></div>`;
  }).join("");
  const merits = (data.merit_history || []).slice(0, 60).map((row) => `<div class="pp-ledger-row"><b class="${row.delta ? "gain" : ""}">${row.delta ? `+${h.numeric(row.delta)}` : "TOTAL"}</b><span>${h.esc(row.system || "—")}</span><strong>${h.numeric(row.total)}</strong><small>${when(row.timestamp)}</small></div>`).join("");
  const cargo = (data.cargo_history || []).slice(0, 60).map((row) => `<div class="pp-ledger-row"><b class="${row.direction === "DELIVER" ? "out" : "in"}">${row.direction === "DELIVER" ? "▼ DELIVER" : "▲ COLLECT"}</b><span>${h.esc(row.type || "—")}<em>${h.esc(row.system || "")}</em></span><strong>${h.numeric(row.count)}</strong><small>${when(row.timestamp)}</small></div>`).join("");
  return `<article class="pp-card pp-timeline"><header><span>MERIT TIMELINE</span><em>${series.length} READINGS · TOTAL MERITS, WITH EACH GAIN BELOW</em></header>${meritChart(series, h)}</article>
    <div class="pp-ledger-pair">
      <article class="pp-card"><header><span>MERIT EVENTS</span><em>${(data.merit_history || []).length} RETAINED</em></header>${merits ? `<div class="pp-ledger">${merits}</div>` : `<p class="pp-empty">Merit changes appear from live journal events.</p>`}</article>
      <article class="pp-card"><header><span>CARGO LEDGER</span><em>${(data.cargo_history || []).length} RETAINED</em></header>${cargo ? `<div class="pp-ledger">${cargo}</div>` : `<p class="pp-empty">Powerplay cargo you collect and deliver appears here.</p>`}</article>
    </div>
    <article class="pp-card pp-archive"><header><span>CYCLE ARCHIVE</span><em>${history.length} CLOSED CYCLES · BEST HIGHLIGHTED</em></header><div class="pp-archive-bars">${archive}</div></article>`;
}

/* POWERS: the twelve leaders, and the one you are reading about. */
function renderPowers(data, h) {
  const dossiers = data.dossiers || [];
  const selected = data.selected_dossier || {};
  const pledgedSlug = (data.pledged_dossier || {}).slug || "";
  const hereSlug = dossiers.find((row) => row.name === (data.location || {}).controlling_power)?.slug || "";
  const tiles = dossiers.map((row) => `<button class="pp-power${row.slug === selected.slug ? " active" : ""}${row.slug === pledgedSlug ? " pledged" : ""}" data-ws-page="powerplay" data-ws-op="select_dossier" data-dossier="${h.esc(row.slug)}" title="${h.esc(row.name)}">
      ${portrait(row.portrait, h)}<span><b>${h.esc(row.name)}</b><small>${h.esc(row.allegiance)}</small></span>
      ${row.slug === pledgedSlug ? `<em class="tag pledge">PLEDGED</em>` : row.slug === hereSlug ? `<em class="tag here">HOLDS THIS SYSTEM</em>` : ""}
    </button>`).join("");
  const ethos = selected.ethos || {};
  const seen = Number(selected.seen_controlled) || 0;
  return `<div class="pp-powers">
    <div class="pp-power-grid">${tiles}</div>
    <article class="pp-dossier${selected.slug === pledgedSlug ? " pledged" : ""}">
      <div class="pp-dossier-face">${portrait(selected.portrait, h)}</div>
      <div class="pp-dossier-body"><small>${h.esc(String(selected.allegiance || "GALACTIC POWER").toUpperCase())} · HQ ${h.esc(String(selected.headquarters || "UNKNOWN").toUpperCase())}</small>
        <h3>${h.esc(selected.name || "Select a power")}</h3><p>${h.esc(selected.role || "")}</p>
        <div class="pp-ethos"><div><span>REINFORCE</span><b>${h.esc(ethos.reinforcement || "—")}</b></div><div><span>ACQUIRE</span><b>${h.esc(ethos.acquisition || "—")}</b></div><div><span>UNDERMINE</span><b>${h.esc(ethos.undermining || "—")}</b></div></div>
        <p class="pp-dossier-note">Ethos is the kind of work each action rewards most for this power.</p>
        <div class="pp-dossier-foot"><span><b>${h.numeric(seen)}</b> ${seen === 1 ? "SYSTEM" : "SYSTEMS"} SEEN UNDER THEIR CONTROL THIS CYCLE</span>${selected.headquarters ? `<button class="pp-ghost ghost" data-ws-page="powerplay" data-ws-op="copy_system" data-system="${h.esc(selected.headquarters)}">COPY HQ SYSTEM</button>` : ""}</div>
      </div>
    </article>
  </div>`;
}

export function renderPowerplayWorkspace(data, ui) {
  const root = ui.byId("powerplay-workspace");
  if (!root) return;
  const h = {esc: ui.escapeHtml, numeric: ui.numeric, credits: ui.credits};
  bind(root);
  const drafts = keepDrafts(root);
  const counts = {
    intel: (data.intel || []).length,
    ops: (data.objectives || []).filter((row) => !row.complete).length,
  };
  const tabs = TABS.map(([key, label]) => `<button type="button" role="tab" data-pp-tab="${key}">${label}${counts[key] ? `<b>${counts[key]}</b>` : ""}</button>`).join("");
  root.classList.remove("loading-panel");
  root.innerHTML = `<section class="pp-workspace">
    ${renderHero(data, h)}
    <nav class="pp-tabs" role="tablist">${tabs}</nav>
    <div class="pp-panel pp-ops" data-pp-panel="ops">${renderSystem(data.location || {}, h)}${renderPulse(data, h)}${renderAssignments(data, h)}</div>
    <div class="pp-panel" data-pp-panel="intel">${renderIntel(data, h)}</div>
    <div class="pp-panel pp-ledgers" data-pp-panel="ledgers">${renderLedgers(data, h)}</div>
    <div class="pp-panel" data-pp-panel="powers">${renderPowers(data, h)}</div>
    <footer class="pp-source">JOURNAL-OBSERVED STANDING AND SYSTEMS · RANK CURVE 2K / 5K / 9K / 15K, THEN +8K PER RANK · COMMANDER-ENTERED ASSIGNMENTS</footer>
  </section>`;
  restoreDrafts(root, drafts);
  applyTab(root);
  applyIntelFilter(root);
  tick();
  if (!ticker) ticker = window.setInterval(tick, 1000);
}
