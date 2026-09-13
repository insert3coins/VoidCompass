function when(value) {
  const parsed = Date.parse(value || "");
  return Number.isFinite(parsed) ? new Date(parsed).toLocaleString() : "UNKNOWN";
}

function remaining(value) {
  const parsed = Date.parse(value || "");
  if (!Number.isFinite(parsed)) return "UNKNOWN";
  const seconds = Math.max(0, Math.floor((parsed - Date.now()) / 1000));
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor(seconds % 86400 / 3600);
  return `${days}D ${hours}H`;
}

export function renderPowerplayWorkspace(data, ui) {
  const {byId, escapeHtml, workspaceMetrics, workspaceCard, workspaceTable, numeric, credits} = ui;
  const root = byId("powerplay-workspace");
  if (!root) return;
  const power = data.powerplay || {};
  const location = data.location || power.location || {};
  const cycle = data.cycle || power.current_cycle || {};
  const dossier = data.selected_dossier || {};
  const pledged = data.pledged_dossier || {};
  const objectives = data.objectives || [];
  const active = data.active_objective || {};
  const dossiers = data.dossiers || [];
  const portrait = pledged.portrait || dossier.portrait || "";
  const identity = pledged.name ? pledged : dossier;

  const dossierRail = dossiers.map((row) => `
    <button class="${row.slug === dossier.slug ? "active" : ""}" data-ws-page="powerplay" data-ws-op="select_dossier" data-dossier="${escapeHtml(row.slug)}" title="${escapeHtml(row.name)}">
      <img src="images/people/powerplay/${escapeHtml(row.portrait)}" alt=""><span><b>${escapeHtml(row.name)}</b><small>${escapeHtml(row.allegiance)}</small></span>
    </button>`).join("");
  const ethos = dossier.ethos || {};
  const dossierPanel = `<article class="powerplay-dossier-detail">
    <img src="images/people/powerplay/${escapeHtml(dossier.portrait || "")}" alt="${escapeHtml(dossier.name || "Power leader")}" onerror="this.hidden=true">
    <div><small>${escapeHtml(dossier.allegiance || "GALACTIC POWER")} · ${escapeHtml(dossier.headquarters || "HQ UNKNOWN")}</small><h3>${escapeHtml(dossier.name || "SELECT A POWER")}</h3><p>${escapeHtml(dossier.role || "Offline Powerplay dossier")}</p>
      <div class="powerplay-ethos"><span><small>REINFORCE</small><b>${escapeHtml(ethos.reinforcement || "—")}</b></span><span><small>ACQUIRE</small><b>${escapeHtml(ethos.acquisition || "—")}</b></span><span><small>UNDERMINE</small><b>${escapeHtml(ethos.undermining || "—")}</b></span></div>
      ${dossier.headquarters ? `<button data-ws-page="powerplay" data-ws-op="copy_system" data-system="${escapeHtml(dossier.headquarters)}">COPY HEADQUARTERS</button>` : ""}
    </div></article>`;

  const assignmentCards = objectives.map((row) => {
    const target = Math.max(1, Number(row.target) || 1), current = Math.max(0, Number(row.current) || 0);
    const progress = Math.max(0, Math.min(100, current * 100 / target));
    return `<article class="powerplay-assignment ${row.complete ? "complete" : ""} ${row.id === active.id ? "selected" : ""}">
      <button class="assignment-select" data-ws-page="powerplay" data-ws-op="select_objective" data-objective-id="${escapeHtml(row.id)}"><span><small>${escapeHtml(String(row.kind || "GENERAL").toUpperCase())}</small><b>${escapeHtml(row.title)}</b><em>${escapeHtml([row.commodity, row.system].filter(Boolean).join(" · ") || "COMMANDER OBJECTIVE")}</em></span><strong>${numeric(current)} / ${numeric(target)}</strong></button>
      <i><span style="width:${progress}%"></span></i><footer><span>${row.complete ? "COMPLETE" : `${numeric(progress, 0)}% COMPLETE`}</span><div><button data-ws-page="powerplay" data-ws-op="toggle_objective" data-objective-id="${escapeHtml(row.id)}">${row.complete ? "REOPEN" : "COMPLETE"}</button><button class="danger-action" data-ws-page="powerplay" data-ws-op="delete_objective" data-objective-id="${escapeHtml(row.id)}">DELETE</button></div></footer>
    </article>`;
  }).join("");

  const assignments = `<form class="powerplay-assignment-form" id="powerplay-assignment-form">
    <label>ASSIGNMENT<input id="powerplay-objective-title" maxlength="160" placeholder="Fortify the target system"></label>
    <label>TYPE<select id="powerplay-objective-kind"><option value="general">GENERAL</option><option value="system">SYSTEM</option><option value="collect">COLLECT CARGO</option><option value="deliver">DELIVER CARGO</option></select></label>
    <label>SYSTEM<input id="powerplay-objective-system" maxlength="140" value="${escapeHtml(location.system || "")}" placeholder="Optional target"></label>
    <label>COMMODITY<input id="powerplay-objective-commodity" maxlength="160" placeholder="Optional cargo match"></label>
    <label>TARGET<input id="powerplay-objective-target" type="number" min="1" max="1000000" value="1"></label>
    <label>NOTES<input id="powerplay-objective-notes" maxlength="500" placeholder="Commander notes"></label>
    <button class="primary" data-ws-page="powerplay" data-ws-op="add_objective">ADD ASSIGNMENT</button>
  </form><div class="powerplay-assignment-grid">${assignmentCards || `<p class="workspace-empty">No assignments yet. Add a system or cargo objective above.</p>`}</div>`;

  const cargo = workspaceTable([
    {label:"Action",key:"direction"},{label:"Commodity",key:"type"},{label:"Count",key:"count"},
    {label:"System",key:"system"},{label:"When",render:(row)=>when(row.timestamp)},
  ], data.cargo_history || [], "Powerplay cargo activity will appear from live Journal events.");
  const merits = workspaceTable([
    {label:"Gain",render:(row)=>row.delta ? `+${numeric(row.delta)}` : "SNAPSHOT"},
    {label:"Total",key:"total"},{label:"System",key:"system"},{label:"When",render:(row)=>when(row.timestamp)},
  ], data.merit_history || [], "Powerplay merit changes will appear from live Journal events.");
  const cycles = workspaceTable([
    {label:"Cycle",key:"id"},{label:"Power",key:"power"},{label:"Merits",key:"merits_gained"},
    {label:"Collected",key:"cargo_collected"},{label:"Delivered",key:"cargo_delivered"},
  ], data.cycle_history || [], "Completed cycle summaries will be retained here.");
  const systems = workspaceTable([
    {label:"System",key:"system"},{label:"Observed merit gain",key:"merits"},
  ], cycle.system_rows || [], "No merit-bearing systems observed this cycle.");

  root.classList.remove("loading-panel");
  root.innerHTML = `<section class="powerplay-workspace">
    <article class="powerplay-identity">${portrait ? `<img src="images/people/powerplay/${escapeHtml(portrait)}" onerror="this.hidden=true">` : ""}<div><small>POWERPLAY 2.0 · JOURNAL OBSERVED</small><h2>${escapeHtml(power.power || "NO ACTIVE PLEDGE")}</h2><p>${power.pledged ? `${escapeHtml(identity.allegiance || "POWER")} · ${escapeHtml(identity.role || "PLEDGED COMMANDER")}` : "No active pledge is retained for this commander profile."}</p><span>${power.last_updated ? `LAST SIGNAL · ${escapeHtml(when(power.last_updated))}` : "AWAITING POWERPLAY JOURNAL DATA"}</span></div></article>
    ${workspaceMetrics([{label:"Rank",value:power.rank==null?"UNKNOWN":numeric(power.rank),detail:"JOURNAL REPORTED"},{label:"Total merits",value:power.merits==null?"UNKNOWN":numeric(power.merits),detail:"PERSISTENT STANDING"},{label:"Cycle gain",value:numeric(cycle.merits_gained),detail:`+${numeric(data.session_merits)} THIS SESSION · ENDS IN ${remaining(cycle.ends)}`},{label:"Salary",value:power.salary==null?"UNKNOWN":credits(power.salary),detail:"LAST PAYMENT"}])}
    <section class="powerplay-dossier-layout"><aside><header><small>OFFLINE REFERENCE</small><b>POWER DOSSIERS</b></header>${dossierRail}</aside>${dossierPanel}</section>
    <section class="workspace-grid two powerplay-live-grid">${workspaceCard("CURRENT POWERPLAY SYSTEM",`<div class="fact-list spacious"><div><span>SYSTEM</span><b>${escapeHtml(location.system || "UNKNOWN")}</b></div><div><span>CONTROLLING POWER</span><b>${escapeHtml(location.controlling_power || "UNKNOWN")}</b></div><div><span>STATE</span><b>${escapeHtml(location.state || "UNKNOWN")}</b></div><div><span>CONTROL PROGRESS</span><b>${location.control_progress==null?"UNKNOWN":`${numeric(Number(location.control_progress)*100,1)}%`}</b></div><div><span>REINFORCEMENT</span><b>${location.reinforcement==null?"UNKNOWN":numeric(location.reinforcement)}</b></div><div><span>UNDERMINING</span><b>${location.undermining==null?"UNKNOWN":numeric(location.undermining)}</b></div></div>${location.system ? `<div class="workspace-actions"><button data-ws-page="powerplay" data-ws-op="copy_system" data-system="${escapeHtml(location.system)}">COPY SYSTEM</button></div>` : ""}`)}${workspaceCard("CURRENT CYCLE",`${workspaceMetrics([{label:"Merits",value:numeric(cycle.merits_gained),detail:"OBSERVED GAIN"},{label:"Collected",value:numeric(cycle.cargo_collected),detail:"UNITS"},{label:"Delivered",value:numeric(cycle.cargo_delivered),detail:"UNITS"}])}${systems}`,`CYCLE ${escapeHtml(cycle.id || "UNKNOWN")}`)}</section>
    ${workspaceCard("ASSIGNMENT BOARD",assignments,`${objectives.filter((row)=>!row.complete).length} ACTIVE`)}
    <section class="workspace-grid two">${workspaceCard("MERIT TIMELINE",merits,`${(data.merit_history || []).length} EVENTS`)}${workspaceCard("CARGO LEDGER",cargo,`${(data.cargo_history || []).length} EVENTS`)}</section>
    ${workspaceCard("CYCLE ARCHIVE",cycles,`${(data.cycle_history || []).length} RETAINED`)}
    <footer class="engineering-suite-source">OFFLINE DOSSIERS · JOURNAL-OBSERVED PROGRESS · COMMANDER-ENTERED ASSIGNMENTS</footer>
  </section>`;
}
