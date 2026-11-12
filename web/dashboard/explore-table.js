/** Dense sortable tables for Explore & Survey (5.7.8), after ED-Outrider's
 * (github.com/weslocke/ED-Outrider, GPLv3): click a heading to sort, and the
 * table fits its box. Narrower, labels shorten (hover for the full text),
 * then the least useful columns go, one level at a time; it never scrolls
 * sideways. Redrawn only when its markup changes, and never while a button
 * in it is held down, so a refresh can't eat a click.
 *
 * A column: {id, label, short?, title?, cell(row) -> html, sort?(row) -> value,
 *            fit?: 0 never hides, 2 hides at level 2, 3 at level 3; cls?}
 */

const LEVELS = 4;
const drawn = new WeakMap();
const held = new WeakSet();
const sorts = new Map();
const labels = new Intl.Collator(undefined, {numeric: true, sensitivity: "base"});
const fitFrames = new WeakMap();

export const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (ch) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[ch]));

/** Both forms of a label: the full one, and the short one compact tables show. */
export function dual(full, short, title = "") {
  if (short === undefined || short === null || short === full) return full;
  const tip = title ? ` title="${esc(title)}"` : "";
  return `<span class="xt-f"${tip}>${full}</span><span class="xt-s"${tip}>${short}</span>`;
}

// A star's class as a coloured pip (the orrery's palette, by spectral letter;
// the odd ones by name), a planet's type as one, and a value as a bar.
const STAR_KINDS = [[/^(n|neutron)/, "N"], [/^(h|black ?hole|supermassive)/, "H"], [/^(d[a-z]*|white dwarf)$/, "D"], [/^w/, "W"],
  [/^(c|cj|cn|ms|s)$/, "C"], [/^(tts|t tauri)/, "TT"], [/^(aebe|herbig)/, "AE"], [/^[obafgkmlty]/, null]];

export function starPip(cls) {
  const text = String(cls || "").trim().toLowerCase();
  if (!text) return "";
  const match = STAR_KINDS.find(([pattern]) => pattern.test(text));
  const kind = match ? match[1] || text.charAt(0).toUpperCase() : "";
  return kind ? `<i class="xt-pip xt-star" data-star="${kind}" aria-hidden="true"></i>` : "";
}

const PLANET_KINDS = [["earth", "elw"], ["water world", "ww"], ["water giant", "wg"], ["ammonia world", "aw"], ["water-based life", "ggw"],
  ["ammonia-based life", "gga"], ["helium", "ggh"], ["gas giant", "gg"], ["high metal", "hmc"], ["metal rich", "metal"], ["metal-rich", "metal"],
  ["rocky ice", "rockice"], ["icy", "icy"], ["rocky", "rocky"]];

export function planetPip(cls) {
  const text = String(cls || "").toLowerCase();
  const kind = PLANET_KINDS.find(([word]) => text.includes(word));
  return kind ? `<i class="xt-pip xt-planet xt-p-${kind[1]}" aria-hidden="true"></i>` : "";
}

export function valueBar(value, top) {
  const share = top > 0 ? Math.max(2, Math.min(100, Math.round(100 * (Number(value) || 0) / top))) : 0;
  return share ? `<i class="xt-vbar" style="--w:${share}%" aria-hidden="true"></i>` : "";
}

export function credits(value) {
  const n = Number(value) || 0;
  if (!n) return "";
  if (n >= 1e9) return `${(n / 1e9).toFixed(n >= 1e10 ? 1 : 2)}B`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(n >= 1e8 ? 0 : 1)}M`;
  if (n >= 1e3) return `${Math.round(n / 1e3)}k`;
  return String(Math.round(n));
}

export function fixed(value, digits = 1) {
  const n = Number(value);
  return Number.isFinite(n) ? n.toLocaleString(undefined, {minimumFractionDigits: digits, maximumFractionDigits: digits}) : "";
}

function storeKey(profile, id) {
  return `voidcompass.explore.sort.${profile}.${id}`;
}

export function sortState(profile, id, fallback) {
  const key = storeKey(profile, id);
  if (!sorts.has(key)) {
    let saved = null;
    try { saved = JSON.parse(localStorage.getItem(key) || "null"); } catch (_error) { saved = null; }
    sorts.set(key, saved && saved.col ? saved : fallback);
  }
  return sorts.get(key);
}

function setSort(profile, id, state) {
  const key = storeKey(profile, id);
  sorts.set(key, state);
  try { localStorage.setItem(key, JSON.stringify(state)); } catch (_error) { /* a convenience only */ }
}

function compare(a, b) {
  if (a === b) return 0;
  if (a === null || a === undefined || a === "") return 1;
  if (b === null || b === undefined || b === "") return -1;
  if (typeof a === "number" && typeof b === "number") return a - b;
  return labels.compare(String(a), String(b));
}

export function sortRows(rows, columns, state) {
  const column = columns.find((col) => col.id === state.col && col.sort);
  if (!column) return rows;
  const sign = state.dir === "desc" ? -1 : 1;
  return rows.map((row, index) => [row, index]).sort((left, right) => {
    const a = column.sort(left[0]);
    const b = column.sort(right[0]);
    // Blanks stay at the bottom whichever way it sorts.
    const blankA = a === null || a === undefined || a === "";
    const blankB = b === null || b === undefined || b === "";
    if (blankA !== blankB) return blankA ? 1 : -1;
    return sign * compare(a, b) || left[1] - right[1];
  }).map(([row]) => row);
}

/** Fit a table to its box: the lowest compact level that doesn't overflow. */
export function fitTable(box) {
  const table = box?.querySelector("table");
  if (!table || !box.clientWidth) return;
  for (let level = 0; level < LEVELS; level += 1) {
    box.dataset.compact = String(level);
    if (table.scrollWidth <= box.clientWidth + 1) return;
  }
}

const fitted = new WeakSet();
function scheduleFit(box) {
  if (fitFrames.has(box)) return;
  fitFrames.set(box, requestAnimationFrame(() => {
    fitFrames.delete(box);
    fitTable(box);
  }));
}

function watchFit(box) {
  if (fitted.has(box) || !("ResizeObserver" in window)) return;
  fitted.add(box);
  let width = -1;
  new ResizeObserver(([entry]) => {
    if (entry.contentRect.width === width) return;
    width = entry.contentRect.width;
    scheduleFit(box);
  }).observe(box);
}

function watchHold(box) {
  if (box.dataset.xtHold) return;
  box.dataset.xtHold = "1";
  box.addEventListener("pointerdown", () => held.add(box));
  const release = () => {
    held.delete(box);
    const pending = box._xtPending;
    if (pending) {
      box._xtPending = null;
      pending();
    }
  };
  box.addEventListener("pointerup", () => setTimeout(release, 0));
  box.addEventListener("pointerleave", release);
}

/** Draw a table into `box`. spec: {id, profile, columns, rows, key(row), rowClass?(row),
 * sort: {col, dir}, empty?: html, onSort?, caption?} */
export function renderTable(box, spec) {
  if (!box) return;
  watchHold(box);
  watchFit(box);
  const draw = () => {
    const state = sortState(spec.profile, spec.id, spec.sort || {col: spec.columns[0]?.id, dir: "asc"});
    const rows = sortRows(spec.rows || [], spec.columns, state);
    const head = spec.columns.map((col) => {
      const sorted = state.col === col.id;
      const label = dual(esc(col.label), col.short !== undefined ? esc(col.short) : undefined, col.title || col.label);
      const arrow = sorted ? (state.dir === "desc" ? " ▾" : " ▴") : "";
      return `<th class="${["xt-c-" + col.id, col.cls || "", col.fit ? `xt-fit${col.fit}` : "", col.sort ? "xt-sortable" : ""].join(" ").trim()}"${col.sort ? ` data-xt-sort="${esc(col.id)}" tabindex="0" aria-sort="${sorted ? (state.dir === "desc" ? "descending" : "ascending") : "none"}"` : ""}${col.title ? ` title="${esc(col.title)}"` : ""}>${label}${arrow}</th>`;
    }).join("");
    const body = rows.map((row) => `<tr data-xt-key="${esc(spec.key(row))}" class="${esc(spec.rowClass ? spec.rowClass(row) : "")}">${spec.columns.map((col) =>
      `<td class="${["xt-c-" + col.id, col.cls || "", col.fit ? `xt-fit${col.fit}` : ""].join(" ").trim()}">${col.cell(row)}</td>`).join("")}</tr>`).join("");
    const markup = `<table class="xt-table" data-xt-id="${esc(spec.id)}"><thead><tr>${head}</tr></thead><tbody>${body || `<tr class="xt-empty"><td colspan="${spec.columns.length}">${spec.empty || "Nothing to show."}</td></tr>`}</tbody></table>`;
    if (drawn.get(box) === markup && box.firstElementChild?.dataset.xtId === spec.id) return;
    drawn.set(box, markup);
    const scroll = box.scrollTop;
    box.innerHTML = markup;
    box.scrollTop = scroll;
    scheduleFit(box);
  };
  if (!box.dataset.xtSortBound) {
    box.dataset.xtSortBound = "1";
    const onSort = (event) => {
      const th = event.target.closest("[data-xt-sort]");
      if (!th || !box.contains(th)) return;
      if (event.type === "keydown" && event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      const current = sortState(box._xtSpec.profile, box._xtSpec.id, box._xtSpec.sort || {});
      const col = th.dataset.xtSort;
      const column = box._xtSpec.columns.find((item) => item.id === col);
      const dir = current.col === col ? (current.dir === "asc" ? "desc" : "asc") : (column?.firstDir || "asc");
      setSort(box._xtSpec.profile, box._xtSpec.id, {col, dir});
      drawn.delete(box);
      box._xtDraw();
      box._xtSpec.onSort?.({col, dir});
    };
    box.addEventListener("click", onSort);
    box.addEventListener("keydown", onSort);
  }
  box._xtSpec = spec;
  box._xtDraw = draw;
  if (held.has(box)) {
    box._xtPending = draw;
    return;
  }
  draw();
}

/** The rows as they're sorted now, for COPY VISIBLE and CSV. */
export function visibleRows(box) {
  const spec = box?._xtSpec;
  if (!spec) return [];
  return sortRows(spec.rows || [], spec.columns, sortState(spec.profile, spec.id, spec.sort || {}));
}

export function toCsv(header, rows) {
  const cell = (value) => {
    const text = String(value ?? "");
    return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  };
  return [header.map(cell).join(","), ...rows.map((row) => row.map(cell).join(","))].join("\r\n");
}

export function downloadText(name, text, type = "text/csv") {
  const blob = new Blob([text], {type: `${type};charset=utf-8`});
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

/** One profile-scoped preference (layout, filters): localStorage, a convenience only. */
export function pref(profile, key, fallback) {
  try {
    const raw = localStorage.getItem(`voidcompass.explore.${key}.${profile}`);
    return raw === null ? fallback : JSON.parse(raw);
  } catch (_error) {
    return fallback;
  }
}

export function setPref(profile, key, value) {
  try { localStorage.setItem(`voidcompass.explore.${key}.${profile}`, JSON.stringify(value)); } catch (_error) { /* convenience */ }
}

/** Fetch one of the deck's data lists (/api/data/<name>). */
export async function fetchData(ui, name, query = {}) {
  const params = new URLSearchParams(Object.entries(query).filter(([, value]) => value !== undefined && value !== null && value !== ""));
  const path = `/api/data/${name}${params.toString() ? `?${params}` : ""}`;
  const url = ui.apiUrl ? ui.apiUrl(path) : path;
  const response = await fetch(url, {cache: "no-store"});
  const text = await response.text();
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return JSON.parse(text);
}
