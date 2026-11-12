/** The Journal Log (5.7.8, ARCHIVE): every journal event as one readable
 * line, newest first, searchable; click one for the raw event. The lines are
 * ED-Outrider's (outrider/log.py, github.com/weslocke/ED-Outrider, GPLv3). */

import {esc, fetchData} from "./explore-table.js";

const CATS = ["travel", "exploration", "phenomena", "bio", "ship", "carrier", "other"];
let st = {ui: null, root: null, rows: [], next: null, q: "", cats: new Set(CATS), days: 30, loading: false, open: ""};

function rowMarkup(row) {
  return `<li class="xl-row xl-${esc(row.cat)}${st.open === row.id ? " open" : ""}" data-xl-id="${esc(row.id)}" tabindex="0">
      <time>${esc(String(row.ts || "").replace("T", " ").slice(0, 19))}</time><b>${esc(row.event)}</b><span>${esc(row.summary || "")}</span>
      ${st.open === row.id ? `<pre class="xl-raw" data-xl-raw>…</pre>` : ""}</li>`;
}

function draw() {
  const list = st.root?.querySelector("[data-xl-list]");
  if (!list) return;
  list.innerHTML = st.rows.map(rowMarkup).join("") || `<li class="workspace-empty">${st.loading ? "Reading your journals…" : "No events match."}</li>`;
  const more = st.root.querySelector("[data-xl-more]");
  if (more) more.hidden = !st.next;
}

async function load(append = false) {
  if (st.loading) return;
  st.loading = true;
  if (!append) {
    st.rows = [];
    st.next = null;
    draw();
  }
  try {
    const data = await fetchData(st.ui, "explore-log", {q: st.q, cats: [...st.cats].join(","), days: st.days, before: append ? st.next : ""});
    st.rows = append ? st.rows.concat(data.rows || []) : data.rows || [];
    st.next = data.next || null;
  } catch (_error) {
    /* left as it was */
  } finally {
    st.loading = false;
    draw();
  }
}

async function showRaw(id) {
  st.open = st.open === id ? "" : id;
  draw();
  if (!st.open) return;
  try {
    const data = await fetchData(st.ui, "explore-log", {raw_of: id});
    const pre = st.root.querySelector("[data-xl-raw]");
    if (pre) pre.textContent = JSON.stringify(data.raw, null, 1);
  } catch (_error) { /* the line stays */ }
}

function bind(root) {
  if (root.dataset.xlBound) return;
  root.dataset.xlBound = "1";
  let timer = 0;
  root.addEventListener("input", (event) => {
    if (!event.target.matches("[data-xl-q]")) return;
    clearTimeout(timer);
    timer = setTimeout(() => {
      st.q = event.target.value.trim();
      load();
    }, 400);
  });
  root.addEventListener("change", (event) => {
    if (event.target.matches("[data-xl-cat]")) {
      if (event.target.checked) st.cats.add(event.target.value); else st.cats.delete(event.target.value);
      load();
    } else if (event.target.matches("[data-xl-days]")) {
      st.days = Number(event.target.value) || 30;
      load();
    }
  });
  root.addEventListener("click", (event) => {
    if (event.target.closest("[data-xl-more]")) {
      load(true);
      return;
    }
    if (event.target.closest("[data-xl-raw]")) return;
    const row = event.target.closest("[data-xl-id]");
    if (row) showRaw(row.dataset.xlId);
  });
}

export function renderJournalLog(panel, ui) {
  if (!panel) return;
  st.ui = ui;
  if (!panel.querySelector(".xl-shell")) {
    panel.innerHTML = `<div class="xl-shell"><div class="xl-bar"><input data-xl-q placeholder="SEARCH THE JOURNAL">
        ${CATS.map((cat) => `<label><input type="checkbox" data-xl-cat value="${cat}" checked> ${cat}</label>`).join("")}
        <select data-xl-days>${[1, 7, 30, 90, 365, 3650].map((d) => `<option value="${d}" ${d === 30 ? "selected" : ""}>${d === 3650 ? "all time" : d === 1 ? "today" : `${d} days`}</option>`).join("")}</select></div>
        <ol class="xl-list" data-xl-list></ol><button type="button" data-xl-more hidden>OLDER</button></div>`;
    st.root = panel;
    bind(panel);
    load();
  }
  st.root = panel;
}
