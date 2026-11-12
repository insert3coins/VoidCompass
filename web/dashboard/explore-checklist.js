/** CHECKLIST (5.7.8): every species by galactic region, what you've done
 * with it there and which colours you still lack; Geology and Phenomena,
 * Canonn's reports by region against your Codex; Canonn's picture of any
 * entry; and My Samples, every sample run with what became of it. After
 * ED-Outrider's checklists and its samples view. Your Codex gaps sit beside it. */

import {credits, downloadText, esc, fetchData, pref, renderTable, setPref, toCsv, visibleRows} from "./explore-table.js";

let st = {ui: null, root: null, profile: "", data: null, samples: null, rev: -1, region: "", picture: "", request: 0};
const lists = new Map();
const samplesByProfile = new Map();
// 5.7.8: Geology and Phenomena beside the organics, after ED-Outrider's lists:
// Canonn's reports by region against your Codex.
const LISTS = [["bio", "ORGANICS"], ["geo", "GEOLOGY"], ["phen", "PHENOMENA"]];

function picButton(row, key) {
  return (row.pictures || []).length ? `<button type="button" class="xc-pic" data-xc-pic="${esc(key)}" title="Canonn's picture of it">📷</button>` : "";
}

function colourDots(row) {
  const here = new Set(row.colours_here || []);
  const any = new Set(row.colours_any || []);
  return (row.colours || []).map((colour) => `<span class="xc-dot ${here.has(colour) ? "here" : any.has(colour) ? "elsewhere" : "none"}" title="${esc(colour)}: ${here.has(colour) ? "logged here" : any.has(colour) ? "logged in another region" : "never logged"}"></span>`).join("");
}

const SPECIES = [
  {id: "genus", label: "GENUS", cell: (row) => esc(row.genus), sort: (row) => row.genus, fit: 3},
  {id: "species", label: "SPECIES", cell: (row) => `<b>${esc(row.species)}</b>`, sort: (row) => row.species},
  {id: "value", label: "VALUE", cell: (row) => credits(row.value), sort: (row) => row.value, cls: "xt-num", firstDir: "desc"},
  {id: "possible", label: "HERE?", cell: (row) => (row.possible === false ? `<span class="xn-dim" title="its rules leave this region out">not here</span>` : row.possible ? "possible" : "?"), sort: (row) => (row.possible === false ? 2 : row.possible ? 0 : 1)},
  {id: "logged", label: "LOGGED HERE", short: "HERE", cell: (row) => (row.logged_here ? "✓" : ""), sort: (row) => (row.logged_here ? 0 : 1)},
  {id: "colours", label: "COLOURS", cell: (row) => `${colourDots(row)} <small>${(row.colours_here || []).length}/${(row.colours || []).length}</small>`, sort: (row) => (row.colours || []).length - (row.colours_here || []).length, firstDir: "desc"},
  {id: "regions", label: "REGIONS", short: "R", cell: (row) => row.regions || "", sort: (row) => row.regions, cls: "xt-num", fit: 2},
  {id: "pic", label: "", cell: (row) => picButton(row, row.species)},
];

const ENTRIES = [
  {id: "group", label: "GROUP", cell: (row) => esc(row.group), sort: (row) => row.group, fit: 3},
  {id: "name", label: "ENTRY", cell: (row) => `<b>${esc(row.name)}</b>`, sort: (row) => row.name},
  {id: "sites", label: "REPORTED HERE", short: "HERE", cell: (row) => (row.sites ? row.sites.toLocaleString() : `<span class="xn-dim">none</span>`), sort: (row) => row.sites, cls: "xt-num", firstDir: "desc"},
  {id: "logged", label: "LOGGED HERE", short: "YOURS", cell: (row) => (row.logged_here ? "✓" : row.logged_any ? `<span class="xn-dim" title="logged in another region">elsewhere</span>` : ""), sort: (row) => (row.logged_here ? 0 : row.logged_any ? 1 : 2)},
  {id: "regions", label: "REGIONS", short: "R", cell: (row) => row.regions || "", sort: (row) => row.regions, cls: "xt-num", fit: 2},
  {id: "pic", label: "", cell: (row) => picButton(row, row.name)},
];

const SAMPLES = [
  {id: "when", label: "WHEN", cell: (row) => esc(String(row.started || "").replace("T", " ").slice(0, 16)), sort: (row) => row.started, firstDir: "desc"},
  {id: "species", label: "SPECIES", cell: (row) => `<b>${esc(row.species)}</b>${row.variant ? ` <small>${esc(row.variant.split(" - ").pop())}</small>` : ""}`, sort: (row) => row.species},
  {id: "where", label: "BODY", cell: (row) => esc(row.body || row.system), sort: (row) => row.body, fit: 2},
  {id: "value", label: "VALUE", cell: (row) => credits(row.sold_for || row.value), sort: (row) => row.sold_for || row.value, cls: "xt-num", firstDir: "desc"},
  {id: "state", label: "STATE", cell: (row) => `<span class="xc-state xc-${esc(row.state)}">${esc(row.state === "sampling" ? `${row.samples}/3` : row.state)}</span>`, sort: (row) => row.state},
];

function filters() {
  return pref(st.profile, "checklist.filters", {missing: false, here_only: true, genus: "", samples: "all", list: "bio"});
}

function listOf() {
  const list = filters().list;
  return LISTS.some(([id]) => id === list) ? list : "bio";
}

function rowsOf(data) {
  return data?.rows || [];
}

function drawPicture() {
  const box = st.root?.querySelector("[data-xc-picture]");
  if (!box) return;
  const list = listOf();
  const row = rowsOf(st.data).find((r) => (list === "bio" ? r.species : r.name) === st.picture);
  const pictures = row?.pictures || [];
  box.hidden = !pictures.length;
  if (!pictures.length) return;
  const title = list === "bio" ? row.species : row.name;
  const key = `${title}|${pictures.length}`;
  if (box._key === key) return;
  box._key = key;
  // Links only: each picture loads from Canonn when it's opened, credited to who took it.
  box.innerHTML = `<header><h4>${esc(title)}</h4><button type="button" data-xc-pic-close title="Close">×</button></header>
    ${pictures.slice(0, 12).map((p) => `<figure><img src="${esc(p.url)}" alt="${esc(title)}${p.colour ? ` (${esc(p.colour)})` : ""}" loading="lazy" referrerpolicy="no-referrer">
      <figcaption>${p.colour ? `<b>${esc(p.colour)}</b> · ` : ""}${p.cmdr ? `Picture: CMDR ${esc(p.cmdr)}` : "Picture"} via Canonn</figcaption></figure>`).join("")}`;
}

function drawEntries() {
  const root = st.root;
  const data = st.data;
  const f = filters();
  const head = root.querySelector("[data-xc-head]");
  if (!head.contains(document.activeElement)) {
    head.innerHTML = `<label>REGION<select data-xc-region>${(data.regions || []).map((name) => `<option ${name === data.region ? "selected" : ""}>${esc(name)}</option>`).join("")}</select></label>
      <b>${data.done_here} of ${data.possible_here}</b><span>${data.list === "phen" ? "phenomena" : "geology entries"} reported in ${esc(data.region)} logged there</span>
      <label><input type="checkbox" data-xc-filter="here_only" ${f.here_only ? "checked" : ""}> reported here only</label>
      <label><input type="checkbox" data-xc-filter="missing" ${f.missing ? "checked" : ""}> missing only</label>
      <small class="xn-dim">Reports: Canonn</small>`;
  }
  const rows = rowsOf(data).filter((row) => (!f.here_only || row.possible) && (!f.missing || !row.logged_here));
  renderTable(root.querySelector("[data-xc-table]"), {id: `checklist-${data.list}`, profile: st.profile, columns: ENTRIES, rows,
    key: (row) => row.name, rowClass: (row) => (row.logged_here ? "xc-done" : ""), sort: {col: "sites", dir: "desc"},
    empty: "Nothing reported in this region."});
}

function drawTabs() {
  const nav = st.root?.querySelector("[data-xc-tabs]");
  if (!nav) return;
  const list = listOf();
  const html = LISTS.map(([id, label]) => `<button type="button" role="tab" data-xc-list="${id}" aria-selected="${id === list}">${label}</button>`).join("");
  if (nav._html !== html) {
    nav._html = html;
    nav.innerHTML = html;
  }
}

function draw() {
  const root = st.root;
  const data = st.data;
  if (!root || !data) return;
  drawTabs();
  drawPicture();
  if ((data.list || "bio") !== "bio") {
    drawEntries();
    drawSamples();
    return;
  }
  const f = filters();
  const head = root.querySelector("[data-xc-head]");
  if (!head.contains(document.activeElement)) {
    const genera = [...new Set((data.rows || []).map((row) => row.genus))].sort();
    head.innerHTML = `<label>REGION<select data-xc-region>${(data.regions || []).map((name) => `<option ${name === data.region ? "selected" : ""}>${esc(name)}</option>`).join("")}</select></label>
      <b>${data.done_here} of ${data.possible_here}</b><span>species possible in ${esc(data.region)} logged there</span>
      <label><input type="checkbox" data-xc-filter="here_only" ${f.here_only ? "checked" : ""}> possible here only</label>
      <label><input type="checkbox" data-xc-filter="missing" ${f.missing ? "checked" : ""}> missing only</label>
      <label>GENUS<select data-xc-genus><option value="">all</option>${genera.map((g) => `<option ${g === f.genus ? "selected" : ""}>${esc(g)}</option>`).join("")}</select></label>`;
  }
  const rows = (data.rows || []).filter((row) => (!f.here_only || row.possible !== false)
    && (!f.missing || !row.logged_here || (row.colours_here || []).length < (row.colours || []).length) && (!f.genus || row.genus === f.genus));
  renderTable(root.querySelector("[data-xc-table]"), {id: "checklist", profile: st.profile, columns: SPECIES, rows,
    key: (row) => row.species, rowClass: (row) => (row.logged_here ? "xc-done" : ""), sort: {col: "genus", dir: "asc"}});
  const geo = root.querySelector("[data-xc-geo]");
  if (geo) geo.innerHTML = (data.geology || []).map((row) =>
    `<div class="xc-geo ${row.logged_here ? "xc-done" : ""}"><span>${row.logged_here ? "✓" : "·"}</span> ${esc(row.name)} <small>${row.regions ? `${row.regions} region${row.regions === 1 ? "" : "s"}` : "never logged"}</small></div>`).join("");
  drawSamples();
}

function drawSamples() {
  const data = st.samples;
  const root = st.root;
  if (!root || !data) return;
  const f = filters();
  const head = root.querySelector("[data-xc-samples-head]");
  if (!head.contains(document.activeElement)) {
    head.innerHTML = `<h4>MY SAMPLES</h4><span>${data.count} runs · ${data.aboard} aboard · ${credits(data.sold_value)} sold · ${data.lost} lost</span>
      <select data-xc-samples>${["all", "aboard", "sampling", "sold", "lost"].map((s) => `<option ${s === f.samples ? "selected" : ""}>${s}</option>`).join("")}</select>
      <button type="button" data-xc-csv>CSV</button>`;
  }
  const rows = (data.rows || []).filter((row) => f.samples === "all" || row.state === f.samples);
  renderTable(root.querySelector("[data-xc-samples-table]"), {id: "samples", profile: st.profile, columns: SAMPLES, rows,
    key: (row) => `${row.started}|${row.species}|${row.body}`, sort: {col: "when", dir: "desc"}, empty: "No sample runs in your journals yet."});
}

function bind(root) {
  if (root.dataset.xcBound) return;
  root.dataset.xcBound = "1";
  root.addEventListener("change", (event) => {
    const f = filters();
    if (event.target.matches("[data-xc-region]")) {
      st.region = event.target.value;
      st.rev = -1;
      renderChecklist(root, st.ui, st.revision);
      return;
    }
    if (event.target.matches("[data-xc-filter]")) setPref(st.profile, "checklist.filters", {...f, [event.target.dataset.xcFilter]: event.target.checked});
    else if (event.target.matches("[data-xc-genus]")) setPref(st.profile, "checklist.filters", {...f, genus: event.target.value});
    else if (event.target.matches("[data-xc-samples]")) setPref(st.profile, "checklist.filters", {...f, samples: event.target.value});
    else return;
    draw();
  });
  root.addEventListener("click", (event) => {
    const tab = event.target.closest("[data-xc-list]");
    if (tab) {
      setPref(st.profile, "checklist.filters", {...filters(), list: tab.dataset.xcList});
      st.picture = "";
      st.rev = -1;
      renderChecklist(root, st.ui, st.revision);
      return;
    }
    if (event.target.closest("[data-xc-retry]")) {
      const samples = samplesByProfile.get(st.profile);
      if (samples && !samples.pending) samples.rev = null;
      st.rev = -1;
      renderChecklist(root, st.ui, st.revision);
      return;
    }
    const pic = event.target.closest("[data-xc-pic]");
    if (pic) {
      st.picture = pic.dataset.xcPic;
      drawPicture();
      return;
    }
    if (event.target.closest("[data-xc-pic-close]")) {
      st.picture = "";
      drawPicture();
      return;
    }
    if (!event.target.closest("[data-xc-csv]")) return;
    const rows = visibleRows(root.querySelector("[data-xc-samples-table]"));
    downloadText("samples.csv", toCsv(["Started", "Analysed", "System", "Body", "Species", "Variant", "State", "Value", "Sold for", "Sold"],
      rows.map((row) => [row.started, row.analysed || "", row.system, row.body, row.species, row.variant, row.state, row.value, row.sold_for || "", row.sold_at || ""])));
  });
}

export function renderChecklist(panel, ui, rev, codexMarkup = "") {
  if (!panel) return;
  const profile = ui.profileKey();
  if (st.profile !== profile) {
    st = {ui, root: panel, profile, data: null, samples: null, rev: -1, region: "", picture: "", request: st.request + 1};
    panel.replaceChildren();
  }
  st.ui = ui;
  st.profile = profile;
  st.revision = rev;
  if (!panel.querySelector(".xc-shell")) {
    panel.innerHTML = `<div class="xc-shell">
        <section class="xc-main xe-card"><nav class="co-tabs xc-tabs" role="tablist" aria-label="Checklist" data-xc-tabs></nav><p class="xc-status" data-xc-status role="status"></p><header class="xc-head" data-xc-head></header><div class="xt-box" data-xc-table></div></section>
        <aside class="xc-side"><section class="xc-picture" data-xc-picture hidden></section><div data-xc-codex></div></aside>
        <section class="xc-samples xe-card"><header class="xc-head" data-xc-samples-head><h4>MY SAMPLES</h4></header><p class="xc-status" data-xc-samples-status role="status"></p><div class="xt-box" data-xc-samples-table></div></section>
      </div>`;
    st.root = panel;
    bind(panel);
    st.rev = -1;
  }
  st.root = panel;
  const codex = panel.querySelector("[data-xc-codex]");
  if (codex && codexMarkup && codex._html !== codexMarkup) {
    codex._html = codexMarkup;
    codex.innerHTML = codexMarkup;
  }
  const list = listOf();
  const key = JSON.stringify([profile, st.region, list]);
  const requestKey = `${key}:${rev}`;
  loadSamples(panel, ui, profile, rev);
  if (requestKey === st.rev) return;
  st.rev = requestKey;
  const request = ++st.request;
  const status = panel.querySelector("[data-xc-status]");
  const cached = lists.get(key);
  st.data = cached?.data || null;
  drawTabs();
  drawPicture();
  if (st.data) draw();
  else {
    panel.querySelector("[data-xc-head]").replaceChildren();
    panel.querySelector("[data-xc-table]").innerHTML = `<p class="workspace-empty">Loading ${esc(LISTS.find(([id]) => id === list)[1].toLowerCase())}…</p>`;
  }
  status.textContent = cached ? "" : "Opening the regional checklist…";
  if (!cached || cached.rev !== rev) {
    const entry = cached?.pending && cached.wanted === rev ? cached : {data: cached?.data || null, rev: cached?.rev, wanted: rev};
    lists.set(key, entry);
    entry.pending ||= fetchData(ui, "explore-checklist", {region: st.region, list});
    entry.pending.then((data) => {
      if (lists.get(key) !== entry) return;
      Object.assign(entry, {data, rev});
      if (lists.size > 24) lists.delete(lists.keys().next().value);
      if (request !== st.request || profile !== st.profile) return;
      st.data = data;
      status.textContent = "";
      draw();
    }).catch(() => {
      if (request !== st.request || profile !== st.profile) return;
      status.innerHTML = `Couldn't load this checklist. <button type="button" data-xc-retry>TRY AGAIN</button>`;
    }).finally(() => { entry.pending = null; });
  }
}

function loadSamples(panel, ui, profile, rev) {
  const cached = samplesByProfile.get(profile);
  const status = panel.querySelector("[data-xc-samples-status]");
  if (cached?.data && st.samples !== cached.data) {
    st.samples = cached.data;
    drawSamples();
  }
  if (cached?.pending) {
    status.textContent = cached.data ? "" : "Reading sample history from your journals…";
    return;
  }
  if (cached?.rev === rev) {
    if (cached.error) status.innerHTML = `Couldn't read sample history. <button type="button" data-xc-retry>TRY AGAIN</button>`;
    return;
  }
  status.textContent = cached?.data ? "" : "Reading sample history from your journals…";
  const entry = {data: cached?.data || null, pending: true, rev: cached?.rev};
  samplesByProfile.set(profile, entry);
  fetchData(ui, "explore-samples").then((data) => {
    Object.assign(entry, {data, rev});
    if (profile !== st.profile || samplesByProfile.get(profile) !== entry) return;
    st.samples = data;
    st.root.querySelector("[data-xc-samples-status]").textContent = "";
    drawSamples();
  }).catch(() => {
    Object.assign(entry, {rev, error: true});
    if (profile !== st.profile || samplesByProfile.get(profile) !== entry) return;
    st.root.querySelector("[data-xc-samples-status]").innerHTML = `Couldn't read sample history. <button type="button" data-xc-retry>TRY AGAIN</button>`;
  }).finally(() => { entry.pending = false; });
}
