/** FIRSTS (5.7.8): your unsold first discoveries, a watch on them (has
 * anyone else's scan reached Spansh? time to sell), what you left behind
 * (Return Later, and biology you didn't finish), and your records. After
 * ED-Outrider's My firsts, Left behind and Your records
 * (github.com/weslocke/ED-Outrider, GPLv3). */

import {credits, esc, fetchData, renderTable} from "./explore-table.js";
import {setSweep} from "./explore-route.js";

let st = {ui: null, root: null, profile: "", data: null, rev: -1, loading: false, ticked: new Set()};

const UNSOLD = [
  {id: "tick", label: "", cell: (row) => `<input type="checkbox" data-xf-pick value="${esc(row.system)}" ${st.ticked.has(row.system) ? "checked" : ""} aria-label="Tick for a sweep">`},
  {id: "system", label: "SYSTEM", cell: (row) => `<b>${esc(row.system)}</b>`, sort: (row) => row.system},
  {id: "bodies", label: "FIRST DISCOVERIES", short: "⚑", cell: (row) => row.bodies, sort: (row) => row.bodies, cls: "xt-num", firstDir: "desc"},
  {id: "mapped", label: "MAPPED", short: "🗺", cell: (row) => row.mapped || "", sort: (row) => row.mapped, cls: "xt-num", fit: 3},
  {id: "value", label: "WORTH", cell: (row) => credits(row.value), sort: (row) => row.value, cls: "xt-num", firstDir: "desc"},
  {id: "first", label: "FOUND", cell: (row) => esc(String(row.first || "").slice(0, 10)), sort: (row) => row.first, fit: 2},
  {id: "act", label: "", cell: (row) => `<span class="xn-acts"><button type="button" data-xf-act="open" data-name="${esc(row.system)}">⌕</button><button type="button" data-xf-act="copy" data-name="${esc(row.system)}">⧉</button></span>`},
];

function leftMarkup(rows) {
  if (!rows?.length) return `<p class="workspace-empty">Nothing left behind: every system you've left is finished, or Return Later has nothing open.</p>`;
  return rows.map((row) => `<article class="xf-left">
      <div><small>${esc(String(row.source || "").toUpperCase())}${row.last_visited ? ` · LAST VISIT ${esc(String(row.last_visited).replace("T", " ").slice(0, 16))}` : ""}</small>
      <h4>${esc(row.system)}</h4>${row.body ? `<b>${esc(row.body)}</b>` : ""}<ul>${(row.reasons || []).map((reason) => `<li>${esc(reason)}</li>`).join("")}</ul></div>
      <div class="xn-acts">
        <button type="button" data-xf-pick-left value="${esc(row.system)}" aria-pressed="${st.ticked.has(row.system)}" title="Tick for a sweep">${st.ticked.has(row.system) ? "☑" : "☐"}</button>
        <button type="button" data-xf-act="copy" data-name="${esc(row.system)}">COPY</button>
        <button type="button" data-xf-act="route" data-name="${esc(row.system)}">ADD TO ROUTE</button>
        ${row.id ? `<button type="button" class="danger-action" data-ws-page="explore" data-ws-op="return_later_dismiss" data-return-later-id="${esc(row.id)}">DISMISS</button>` : ""}
      </div></article>`).join("");
}

function recordsMarkup(rows) {
  if (!rows?.length) return `<p class="workspace-empty">Your records appear as you scan.</p>`;
  return `<div class="xf-records">${rows.map((row) => `<div class="xf-record"><small>${esc(row.label)}</small><b>${esc(row.text)}</b><span>${esc(row.body || row.system || "")}</span></div>`).join("")}</div>`;
}

function draw() {
  const root = st.root;
  const data = st.data;
  if (!root || !data) return;
  renderTable(root.querySelector("[data-xf-unsold]"), {
    id: "firsts", profile: st.profile, columns: UNSOLD, rows: data.unsold || [], key: (row) => row.system,
    sort: {col: "value", dir: "desc"}, empty: "No unsold first discoveries since your last sale.",
  });
  const total = (data.unsold || []).reduce((sum, row) => sum + (row.value || 0), 0);
  root.querySelector("[data-xf-unsold-head]").innerHTML = `<h4>UNSOLD FIRSTS</h4><span>${(data.unsold || []).length} systems · ${credits(total) || "0"} cr${data.last_sale ? ` since your last sale (${esc(String(data.last_sale).slice(0, 10))})` : ""}</span>`;
  const watch = data.watch || {};
  root.querySelector("[data-xf-watch]").innerHTML = `<header><h4>FIRSTS WATCH</h4><button type="button" data-ws-page="explore" data-ws-op="firsts_watch">CHECK NOW</button></header>
    <p class="xn-status">${esc(watch.detail || "Has someone else's scan of your unsold first discoveries reached Spansh? If it has, time to go and sell.")}</p>
    ${(watch.rows || []).map((row) => `<div class="xf-watch-row">⚠ <b>${esc(row.system)}</b> on Spansh since ${esc(row.updated)} · ${credits(row.value)} at risk</div>`).join("")}`;
  const left = root.querySelector("[data-xf-left]");
  const leftHtml = leftMarkup(data.left);
  if (left._html !== leftHtml) {
    left._html = leftHtml;
    left.innerHTML = leftHtml;
  }
  root.querySelector("[data-xf-records]").innerHTML = recordsMarkup(data.records);
  drawSweep();
}

function drawSweep() {
  const bar = st.root?.querySelector("[data-xf-sweepbar]");
  if (bar) bar.innerHTML = st.ticked.size ? `<span>${st.ticked.size} ticked</span><button type="button" class="primary" data-xf-sweep>PLOT A SWEEP THROUGH THEM</button>` : "";
}

function bind(root) {
  if (root.dataset.xfBound) return;
  root.dataset.xfBound = "1";
  root.addEventListener("change", (event) => {
    if (event.target.matches("[data-xf-pick]")) {
      if (event.target.checked) st.ticked.add(event.target.value); else st.ticked.delete(event.target.value);
      drawSweep();
    }
  });
  root.addEventListener("click", async (event) => {
    const ui = st.ui;
    const pick = event.target.closest("[data-xf-pick-left]");
    if (pick) {
      if (st.ticked.has(pick.value)) st.ticked.delete(pick.value); else st.ticked.add(pick.value);
      st.root.querySelector("[data-xf-left]")._html = "";
      draw();
      return;
    }
    if (event.target.closest("[data-xf-sweep]")) {
      const systems = [...st.ticked];
      setSweep(st.profile, systems);
      await ui.command("workspace", {page: "explore", operation: "plot_route", plotter: "sweep", systems});
      ui.setView?.("route");
      return;
    }
    const act = event.target.closest("[data-xf-act]");
    if (!act) return;
    const name = act.dataset.name;
    if (act.dataset.xfAct === "open") {
      ui.openSystem?.(name);
      return;
    }
    const op = {copy: "copy_system", route: "add_route"}[act.dataset.xfAct];
    if (await ui.command("workspace", {page: "explore", operation: op, name})) ui.showToast?.(op === "copy_system" ? `${name} copied` : `${name} added to your route`);
  });
}

export function renderFirsts(panel, ui, rev) {
  if (!panel) return;
  st.ui = ui;
  st.profile = ui.profileKey();
  if (!panel.querySelector(".xf-shell")) {
    panel.innerHTML = `<div class="xf-shell">
        <section class="xf-col xe-card"><header class="xf-head" data-xf-unsold-head></header><div class="xf-sweepbar" data-xf-sweepbar></div><div class="xt-box" data-xf-unsold></div><section class="xf-watch" data-xf-watch></section></section>
        <section class="xf-col xe-card xf-left-card"><header class="xf-head"><h4>LEFT BEHIND</h4><span>Return Later, and biology you didn't finish</span></header><div class="xf-left-list" data-xf-left></div></section>
        <section class="xf-col xe-card xf-records-card"><header class="xf-head"><h4>YOUR RECORDS</h4><span>The most extreme bodies you've scanned</span></header><div class="xf-records-body" data-xf-records></div></section>
      </div>`;
    st.root = panel;
    bind(panel);
    st.rev = -1;
  }
  st.root = panel;
  if (rev === st.rev || st.loading) return;
  st.rev = rev;
  st.loading = true;
  fetchData(ui, "explore-firsts").then((data) => {
    st.data = data;
    draw();
  }).catch(() => {}).finally(() => { st.loading = false; });
}
