/** History (5.7.8): the books. One row a session (expand it for the systems
 * it found first and its highlights), the summary rows, trips from sale to
 * sale, your top 25 finds and records, the trip as Markdown, CSV exports and
 * an EDSM flight log import. */

import {credits, downloadText, esc, fetchData, fixed, renderTable, toCsv} from "./explore-table.js";

let st = {ui: null, profile: "", data: null, period: "all", open: "", loading: false, polling: 0, fetched: 0};

const SESSIONS = [
  {id: "started", label: "SESSION", cell: (r) => `<button type="button" class="hs-open" data-hs-open="${esc(r.started)}" aria-expanded="${st.open === r.started}">${st.open === r.started ? "▾" : "▸"}</button> ${esc(r.started.replace("T", " ").slice(0, 16))}${st.open === r.started ? sessionDetail(r) : ""}`, sort: (r) => r.started, firstDir: "desc"},
  {id: "jumps", label: "JUMPS", cell: (r) => r.jumps, sort: (r) => r.jumps, cls: "xt-num", firstDir: "desc"},
  {id: "ly", label: "LY", cell: (r) => Math.round(r.ly).toLocaleString(), sort: (r) => r.ly, cls: "xt-num", firstDir: "desc"},
  {id: "far", label: "MAX FROM SOL", short: "SOL", cell: (r) => (r.far !== null ? r.far.toLocaleString() : ""), sort: (r) => r.far, cls: "xt-num", fit: 2},
  {id: "firsts", label: "FIRST SYSTEMS", short: "⚑", cell: (r) => r.firsts || "", sort: (r) => r.firsts, cls: "xt-num", firstDir: "desc"},
  {id: "bodies", label: "BODIES", cell: (r) => r.bodies || "", sort: (r) => r.bodies, cls: "xt-num", firstDir: "desc", fit: 3},
  {id: "mapped", label: "MAPPED", short: "🗺", cell: (r) => r.mapped || "", sort: (r) => r.mapped, cls: "xt-num", firstDir: "desc"},
  {id: "footfalls", label: "FOOTFALLS", short: "👣", cell: (r) => r.footfalls || "", sort: (r) => r.footfalls, cls: "xt-num", firstDir: "desc", fit: 2},
  {id: "species", label: "SPECIES", short: "🧬", cell: (r) => r.species || "", sort: (r) => r.species, cls: "xt-num", firstDir: "desc"},
  {id: "sold", label: "SOLD", cell: (r) => credits(r.sold), sort: (r) => r.sold, cls: "xt-num", firstDir: "desc"},
  {id: "codex", label: "CODEX", cell: (r) => r.codex || "", sort: (r) => r.codex, cls: "xt-num", fit: 3},
  {id: "deaths", label: "DEATHS", cell: (r) => (r.deaths ? `<span class="xb-high">${r.deaths}</span>` : ""), sort: (r) => r.deaths, cls: "xt-num"},
];

function sessionDetail(r) {
  return `<div class="hs-detail"><div>${esc(r.start_system || "")} → ${esc(r.end_system || "")}${r.ship ? ` · ${esc(r.ship)}` : ""}</div>
    ${r.first_systems?.length ? `<div><b>First discoveries:</b> ${esc(r.first_systems.join(", "))}</div>` : ""}
    ${(r.highlights || []).map((h) => `<div class="xn-dim">· ${esc(h.title || h.text || h.label || "")}</div>`).join("")}</div>`;
}

const TRIPS = [
  {id: "end", label: "SOLD", cell: (r) => esc(r.end.replace("T", " ").slice(0, 16)), sort: (r) => r.end, firstDir: "desc"},
  {id: "paid", label: "PAID", cell: (r) => `<b>${credits(r.paid)}</b>`, sort: (r) => r.paid, cls: "xt-num", firstDir: "desc"},
  {id: "estimate", label: "OUR ESTIMATE", short: "EST", cell: (r) => credits(r.estimate), sort: (r) => r.estimate, cls: "xt-num", fit: 2},
  {id: "bonus", label: "×5 PAID / PREDICTED", short: "×5", cell: (r) => (r.samples ? `${r.bonus_samples} / ${r.predicted_bonus}` : ""), cls: "xt-num", fit: 2},
  {id: "crh", label: "CR/H", cell: (r) => credits(r.cr_h), sort: (r) => r.cr_h, cls: "xt-num", firstDir: "desc"},
  {id: "crj", label: "CR/JUMP", cell: (r) => credits(r.cr_jump), sort: (r) => r.cr_jump, cls: "xt-num", fit: 3},
  {id: "jumps", label: "JUMPS", cell: (r) => r.jumps, sort: (r) => r.jumps, cls: "xt-num"},
  {id: "deaths", label: "DEATHS", cell: (r) => (r.deaths ? `<span class="xb-high">${r.deaths}</span>` : ""), sort: (r) => r.deaths, cls: "xt-num"},
];

const TOP = [
  {id: "value", label: "WORTH", cell: (r) => `<b>${credits(r.value)}</b>`, sort: (r) => r.value, cls: "xt-num", firstDir: "desc"},
  {id: "body", label: "BODY", cell: (r) => `${esc(r.system)} <b>${esc(r.body)}</b>${r.first ? " ⚑" : ""}`, sort: (r) => r.body},
  {id: "class", label: "CLASS", cell: (r) => esc(r.class || ""), sort: (r) => r.class, fit: 2},
  {id: "when", label: "WHEN", cell: (r) => esc(r.when), sort: (r) => r.when, fit: 3},
];

function summaryMarkup(rows) {
  const cell = (value) => (value === null || value === undefined ? "—" : typeof value === "number" ? Math.round(value).toLocaleString() : esc(value));
  return `<table class="xt-table hs-summary"><thead><tr><th></th><th class="xt-num">JUMPS</th><th class="xt-num">LY</th><th class="xt-num">MAX FROM SOL</th><th class="xt-num">FIRST SYSTEMS</th><th class="xt-num">BODIES</th><th class="xt-num">MAPPED</th><th class="xt-num">FOOTFALLS</th><th class="xt-num">SPECIES</th><th class="xt-num">SOLD</th><th class="xt-num">CODEX</th><th class="xt-num">DEATHS</th></tr></thead>
    <tbody>${(rows || []).map((r) => `<tr><td><b>${esc(r.label)}</b></td>${["jumps", "ly", "far", "firsts", "bodies", "mapped", "footfalls", "species"].map((k) => `<td class="xt-num">${cell(r[k])}</td>`).join("")}<td class="xt-num">${credits(r.sold) || "—"}</td><td class="xt-num">${cell(r.codex)}</td><td class="xt-num">${cell(r.deaths)}</td></tr>`).join("")}</tbody></table>`;
}

function draw(slot) {
  const data = st.data;
  if (!data) {
    slot.innerHTML = `<p class="workspace-empty">Reading your history…</p>`;
    return;
  }
  if (!slot.querySelector(".hs-shell")) {
    slot.innerHTML = `<div class="hs-shell">
      <div class="hs-bar"><label>PERIOD<select data-hs-period></select></label>
        <button type="button" data-ws-page="explore" data-ws-op="history_copy_trip" title="The 'since your last sale' row as Markdown, for Reddit or Discord">COPY THE TRIP</button>
        <span>CSV:</span>${["firsts", "jumps", "codex", "trips", "route", "unsold"].map((kind) => `<button type="button" data-hs-csv="${kind}">${kind.toUpperCase()}</button>`).join("")}
      </div>
      <div data-hs-summary></div>
      <h4 class="cmdr-h">SESSIONS</h4><div class="xt-box hs-box" data-hs-sessions></div>
      <div class="workspace-grid two">
        <section><h4 class="cmdr-h">TRIPS · SALE TO SALE</h4><div class="xt-box hs-box" data-hs-trips></div></section>
        <section><h4 class="cmdr-h">TOP 25 FINDS</h4><div class="xt-box hs-box" data-hs-top></div></section>
      </div>
      <section><h4 class="cmdr-h">YOUR RECORDS</h4><div class="xf-records hs-records" data-hs-records></div></section>
      <section class="hs-edsm"><h4 class="cmdr-h">BEFORE YOUR JOURNALS · EDSM FLIGHT LOG</h4><div data-hs-edsm></div></section>
    </div>`;
  }
  const select = slot.querySelector("[data-hs-period]");
  if (select && document.activeElement !== select) select.innerHTML = (data.periods || ["all"]).map((p) => `<option ${p === st.period ? "selected" : ""}>${p}</option>`).join("");
  slot.querySelector("[data-hs-summary]").innerHTML = summaryMarkup(data.summary);
  renderTable(slot.querySelector("[data-hs-sessions]"), {id: "hs-sessions", profile: st.profile, columns: SESSIONS, rows: data.sessions || [],
    key: (r) => r.started, sort: {col: "started", dir: "desc"}, empty: "No sessions in the Captain's Log yet."});
  renderTable(slot.querySelector("[data-hs-trips]"), {id: "hs-trips", profile: st.profile, columns: TRIPS, rows: data.trips || [],
    key: (r) => r.end, sort: {col: "end", dir: "desc"}, empty: data.books_ready ? "No two sales of exploration or biology yet." : "Reading your journals…"});
  renderTable(slot.querySelector("[data-hs-top]"), {id: "hs-top", profile: st.profile, columns: TOP, rows: data.top || [],
    key: (r) => `${r.system}|${r.body}`, sort: {col: "value", dir: "desc"}});
  slot.querySelector("[data-hs-records]").innerHTML = (data.records || []).map((r) => `<div class="xf-record"><small>${esc(r.label)}</small><b>${esc(r.text)}</b><span>${esc(r.body || r.system || "")}</span></div>`).join("") || "<p class='workspace-empty'>Your records appear as you scan.</p>";
  const e = data.edsm || {};
  slot.querySelector("[data-hs-edsm]").innerHTML = `<p>${e.count ? `${e.count.toLocaleString()} visits to ${e.systems.toLocaleString()} systems from before your journals, imported ${esc(String(e.imported || "").slice(0, 10))}. They're kept apart from your journal data.` : "Visits from before your journals can come from your EDSM flight log (it needs your EDSM API key in Settings › Integrations)."}</p>
    <p class="xn-status">${esc(e.detail || "")}</p><button type="button" data-ws-page="explore" data-ws-op="history_edsm_import" ${e.status === "working" ? "disabled" : ""}>${e.status === "working" ? "IMPORTING…" : e.count ? "IMPORT AGAIN" : "IMPORT FROM EDSM"}</button>${e.count ? ` <button type="button" data-hs-csv="edsm">CSV</button>` : ""}`;
}

async function load(slot) {
  if (st.loading) return;
  st.loading = true;
  try {
    st.data = await fetchData(st.ui, "history", {period: st.period});
  } catch (_error) { /* asked again */ } finally {
    st.loading = false;
  }
  draw(slot);
  clearTimeout(st.polling);
  if (st.data && (!st.data.books_ready || st.data.edsm?.status === "working")) st.polling = setTimeout(() => load(slot), 3000);
}

function bind(page, slot) {
  if (page.dataset.hsBound) return;
  page.dataset.hsBound = "1";
  page.addEventListener("click", async (event) => {
    const open = event.target.closest("[data-hs-open]");
    if (open) {
      st.open = st.open === open.dataset.hsOpen ? "" : open.dataset.hsOpen;
      draw(slot);
      return;
    }
    const csv = event.target.closest("[data-hs-csv]");
    if (csv) {
      try {
        const data = await fetchData(st.ui, "history-export", {kind: csv.dataset.hsCsv});
        downloadText(`${csv.dataset.hsCsv}.csv`, toCsv(data.header, data.rows));
      } catch (error) {
        st.ui.showToast?.(`Couldn't export: ${error.message}`);
      }
    }
  });
  page.addEventListener("change", (event) => {
    if (!event.target.matches("[data-hs-period]")) return;
    st.period = event.target.value;
    load(slot);
  });
}

function apply(page, slot) {
  // Never a blank page while the first answer is on its way.
  if (!st.data && !slot.textContent.trim()) draw(slot);
  if (!st.data || Date.now() - st.fetched > 20000) {
    st.fetched = Date.now();
    load(slot);
  }
}

/** Called whenever the History page redraws. */
export function renderHistory(ui, profile) {
  const page = document.querySelector('[data-page-name="chronicle"]');
  const slot = document.getElementById("history-workspace");
  if (!page || !slot) return;
  st.ui = ui;
  if (st.profile !== profile) {
    st.profile = profile;
    st.data = null;
  }
  bind(page, slot);
  apply(page, slot);
}
