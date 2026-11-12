/** The body table (5.7.8): every body of one system, sortable, for OVERVIEW's
 * right-hand pane and the SYSTEM tab. Rows come from /api/data/explore-system:
 * your scans laid over Spansh's dump. After ED-Outrider's Here view
 * (github.com/weslocke/ED-Outrider, GPLv3). */

import {credits, dual, esc, fetchData, fixed, planetPip, pref, renderTable, setPref, starPip, toCsv, downloadText, valueBar, visibleRows} from "./explore-table.js";

// A species' colour shows in that colour: these are the game's own colour
// names, so they're data, not theme.
const SPECIES_COLOURS = {
  lime: "#9be35a", teal: "#3fc9b8", green: "#4fc76a", emerald: "#38b878", yellow: "#e9d44a", gold: "#e5b84a",
  orange: "#ef9a3c", amber: "#e8a33a", red: "#e05a4f", maroon: "#b34a5c", mulberry: "#b0507e", grey: "#a7adb3",
  white: "#e8edf2", blue: "#5d9cf0", cobalt: "#4a72e0", indigo: "#7b6ef0", aquamarine: "#5fe0c8", turquoise: "#45d0d0",
  cyan: "#4fd8e8", sage: "#9fb88a", ocher: "#c99a4a", ochre: "#c99a4a", peach: "#f0a888", magenta: "#e05ad0",
  lavender: "#b9a2f0", amethyst: "#a76ee0", black: "#8a8f96", brown: "#a87a4f", silver: "#c8ccd2", violet: "#a06ef0",
};

const MARKS = {
  scoop: ["⛽", "a scoopable star"], rings: ["◎", "rings"], hotspots: ["✸", "ring hotspots"],
  first_discovered: ["⚑", "first discovered by you"], first_mapped: ["🗺", "first mapped by you"],
  footfall_open: ["👣", "nobody has walked here yet"], done: ["✓", "species analysed"],
  sampling: ["◔", "samples under way (n/3)"], guess: ["?", "the likeliest species, not yet known"],
  codex: ["✦", "new to your Codex (✪ anywhere)"], ggg: ["🟢", "a (potential) green gas giant"],
  record: ["🏆", "one of your records"], terraformable: ["T", "terraformable"], landable: ["⬇", "landable"],
  geo: ["⛰", "geological signals"], high_g: ["g", "high gravity"],
};

function bioCell(row) {
  const cells = (row.bio || []).map((cell) => {
    const colour = SPECIES_COLOURS[String(cell.colour || "").toLowerCase()];
    const mark = cell.state === "done" ? "✓ " : cell.state === "sampling" ? `${cell.progress}/3 ` : cell.state === "guess" ? "? " : "";
    const label = `${esc(cell.name)}${cell.colour ? ` <span class="xb-colour"${colour ? ` style="color:${colour}"` : ""}>${esc(cell.colour)}</span>` : ""}`;
    const value = cell.value ? ` <small>${credits(cell.value)}</small>` : "";
    return `<div class="xb-bio xb-${esc(cell.state)}" title="${esc(cell.state === "guess" ? "The likeliest species, not yet known" : cell.state)}">${mark}${label}${value}</div>`;
  });
  const left = row.bio_count - (row.bio || []).filter((cell) => cell.state !== "guess").length;
  if (row.bio_count && !(row.bio || []).length) cells.push(`<div class="xb-bio">${row.bio_count} bio</div>`);
  else if (left > 0 && (row.bio || []).every((cell) => cell.state === "guess")) cells.unshift(`<div class="xb-dim">${row.bio_count} bio signal${row.bio_count === 1 ? "" : "s"}</div>`);
  if (row.geo_count) cells.push(`<div class="xb-geo">⛰ ${row.geo_count} geo${row.geo_new?.length ? ` <span class="xb-codex" title="new to your Codex here: ${esc(row.geo_new.join(", "))}">✦</span>` : ""}</div>`);
  return cells.join("");
}

function nameCell(row) {
  const marks = [
    row.record ? `<span title="${esc(row.record)}">🏆</span>` : "",
    row.codex_type ? `<span class="xb-codex" title="${esc(row.codex_type_name || row.cls)}: new to your Codex ${row.codex_type === "new" ? "anywhere" : "in this region"}">${row.codex_type === "new" ? "✪" : "✦"}</span>` : "",
    row.green ? `<span title="a green gas giant (your Codex says so)">🟢</span>` : row.ggg ? `<span title="a potential green gas giant (${esc(row.ggg.chance)}): a cloud layer sits on a colour border at ${esc(row.ggg.border)} K. A guess from the community's model (CMDR Regza, Dr. K. Ross, CMDR Arcanic, Canonn); the Codex confirms it">🟢?</span>` : "",
    row.landable ? `<span class="xb-dim" title="landable">⬇</span>` : "",
  ].join("");
  return `<b class="xb-name">${esc(row.name || "—")}</b>${marks ? ` <span class="xb-marks">${marks}</span>` : ""}`;
}

function classCell(row) {
  if (row.kind === "star") return `${starPip(row.cls)}${esc(row.cls || "★")}${row.scoop ? ` <span class="xb-scoop" title="scoopable">⛽</span>` : ""}`;
  const full = esc(row.cls || "");
  const short = esc(row.short || row.cls || "");
  return `${planetPip(row.cls_full || row.cls)}${dual(full, short, row.cls_full)}${row.terraformable ? ` <span class="xb-tf" title="terraformable">T</span>` : ""}${row.pre_odyssey ? ` <span class="xb-old" title="Spansh's report predates Odyssey: biology may be missing">⏳</span>` : ""}`;
}

function distanceCell(row) {
  const main = row.dist_ls === null || row.dist_ls === undefined ? "" : Math.round(row.dist_ls).toLocaleString();
  const parent = row.parent ? `<div class="xb-parent" title="its orbit round ${esc(row.parent.name)}">↳ ${row.parent.ls !== null && row.parent.ls !== undefined ? `${fixed(row.parent.ls, row.parent.ls < 10 ? 1 : 0)} ls · ` : ""}${esc(row.parent.name)}</div>` : "";
  return `${main}${parent}`;
}

function gravityCell(row, meta) {
  if (row.gravity === null || row.gravity === undefined || row.kind === "star") return "";
  const high = row.gravity >= (meta.high_gravity || 2);
  return `<span class="${high ? "xb-high" : ""}">${fixed(row.gravity, 2)}</span>`;
}

function ringsCell(row) {
  const rings = (row.rings || []).length;
  if (!rings) return "";
  return `<span title="${esc(row.rings.map((ring) => `${ring.name}: ${ring.type}`).join("\n"))}">◎${rings}</span>${row.hotspots ? ` <span class="xb-hot" title="ring hotspots">✸${row.hotspots}</span>` : ""}`;
}

function firstsCell(row) {
  return [row.first_discovered ? `<span title="first discovered by you">⚑</span>` : "",
    row.first_mapped ? `<span title="first mapped by you">🗺</span>` : "",
    row.footfall_open ? `<span title="nobody has walked here: first footfall is open">👣</span>` : ""].join("");
}

export const BODY_COLUMNS = (meta) => [
  // The suggested order to fly them in, by where they are now (5.7.8).
  ...(meta.ordered ? [{id: "order", label: "→", title: "Suggested order: the bodies with work left, nearest first by where they are now", cell: (row) => (row.order ? `<span class="xb-order" title="${row.leg_ls ? `${row.leg_ls.toLocaleString()} ls from the last` : ""}">${row.order}</span>` : ""), sort: (row) => row.order ?? null, cls: "xt-num"}] : []),
  {id: "name", label: "BODY", cell: nameCell, sort: (row) => row.name},
  {id: "cls", label: "CLASS", cell: classCell, sort: (row) => row.cls, fit: 0},
  {id: "dist", label: "DIST LS", short: "LS", cell: distanceCell, sort: (row) => row.dist_ls, cls: "xt-num"},
  {id: "grav", label: "GRAV", short: "G", cell: (row) => gravityCell(row, meta), sort: (row) => row.gravity, cls: "xt-num", firstDir: "desc"},
  {id: "bio", label: "BIO / GEO", cell: bioCell, sort: (row) => row.bio_count * 10 + row.geo_count, firstDir: "desc"},
  {id: "rings", label: "RINGS", short: "◎", cell: ringsCell, sort: (row) => (row.rings || []).length, fit: 3, firstDir: "desc"},
  {id: "firsts", label: "FIRSTS", short: "⚑", cell: firstsCell, sort: (row) => (row.first_discovered ? 2 : 0) + (row.first_mapped ? 1 : 0), fit: 2, firstDir: "desc"},
  {id: "now", label: "NOW", cell: (row) => credits(row.value_now), sort: (row) => row.value_now || null, cls: "xt-num", fit: 3, firstDir: "desc"},
  {id: "max", label: "MAX", cell: (row) => `<b>${credits(row.value_max)}</b>${valueBar(row.value_max, meta.top)}`, sort: (row) => row.value_max || null, cls: "xt-num", firstDir: "desc"},
];

/** Rows as a tree: each body under the one it orbits. */
function treeOrder(rows) {
  const byName = new Map(rows.map((row) => [String(row.name), row]));
  const children = new Map();
  const roots = [];
  for (const row of rows) {
    const parent = row.parent && byName.get(String(row.parent.name));
    if (parent && parent !== row) {
      if (!children.has(parent)) children.set(parent, []);
      children.get(parent).push(row);
    } else {
      roots.push(row);
    }
  }
  const out = [];
  const walk = (row, depth) => {
    out.push({...row, depth});
    for (const child of (children.get(row) || []).sort((a, b) => (a.dist_ls || 0) - (b.dist_ls || 0))) walk(child, depth + 1);
  };
  roots.sort((a, b) => (a.dist_ls || 0) - (b.dist_ls || 0)).forEach((row) => walk(row, 0));
  return out;
}

export function headingMarkup(data, ui, mode) {
  const meta = data.meta || {};
  const known = meta.body_count ? `${meta.known} of ${meta.body_count} bodies known` : `${meta.known || 0} bodies known`;
  const spansh = meta.spansh_known ? `Spansh: ${esc(meta.spansh_date || "no date")}` : data.status === "working" ? "asking Spansh…" : meta.spansh_error ? `Spansh: ${esc(meta.spansh_error)}` : "yours only";
  const modes = [["list", "≡ LIST"], ["tree", "⋔ TREE"], ["schematic", "◉ SCHEMATIC"]]
    .map(([id, label]) => `<button type="button" data-xb-mode="${id}" aria-pressed="${mode === id}">${label}</button>`).join("");
  return `<div class="xb-head-main"><small>VIEWING</small>
      <button type="button" class="xb-star" data-explore-bookmark="${esc(data.system)}" aria-pressed="${Boolean(data.bookmarked)}" title="Bookmark">${data.bookmarked ? "★" : "☆"}</button>
      <b>${esc(data.system || "—")}</b>${data.here ? `<em class="xb-here">HERE</em>` : ""}
      <span>${known} · ${spansh} · now <b>${credits(meta.value_now) || "0"}</b> · max <b>${credits(meta.value_max) || "0"}</b></span>
      ${meta.pre_odyssey ? `<em class="xb-old" title="Every report Spansh has of it predates Odyssey (29 Nov 2022): fully scanned may still hide biology and first footfalls">PRE-ODYSSEY</em>` : ""}
    </div>
    <div class="xb-head-tools">
      <button type="button" data-xb-csv title="Download the table as CSV">CSV</button>
      <button type="button" data-ws-page="explore" data-ws-op="system_summary" data-name="${esc(data.system)}" title="Copy a short Markdown write-up">COPY SUMMARY</button>
      <button type="button" data-ws-page="explore" data-ws-op="copy_system" data-name="${esc(data.system)}">COPY</button>
      <button type="button" data-ws-page="explore" data-ws-op="system_refresh" data-name="${esc(data.system)}" title="Ask Spansh again">↻</button>
      <span class="xb-modes" role="group" aria-label="Table layout">${modes}</span>
    </div>`;
}

export function legendMarkup(keys) {
  return (keys || []).filter((key) => MARKS[key]).map((key) => `<span><b>${MARKS[key][0]}</b> ${esc(MARKS[key][1])}</span>`).join("");
}

/** Draw a system's table into a pane: {head, table, legend} elements. */
export function renderBodies(pane, data, ui, {profile, id = "bodies", onRow} = {}) {
  if (!pane || !data) return;
  const mode = pref(profile, `${id}.mode`, "list");
  const head = pane.querySelector("[data-xb-head]");
  const box = pane.querySelector("[data-xb-table]");
  const legend = pane.querySelector("[data-xb-legend]");
  const headHtml = headingMarkup(data, ui, mode);
  if (head && head._html !== headHtml) {
    head._html = headHtml;
    head.innerHTML = headHtml;
  }
  const meta = {...(data.meta || {}), top: Math.max(0, ...(data.rows || []).map((row) => Number(row.value_max) || 0))};
  let columns = BODY_COLUMNS(meta);
  let rows = data.rows || [];
  if (mode === "tree") {
    rows = treeOrder(rows);
    columns = columns.map((col) => ({...col, sort: undefined}));
    columns[0] = {...columns[0], cell: (row) => `<span class="xb-indent" style="--depth:${row.depth || 0}"></span>${nameCell(row)}`};
  }
  renderTable(box, {
    id, profile, columns, rows, key: (row) => row.key,
    rowClass: (row) => [row.own ? "xb-own" : "xb-spansh", row.kind, row.first_discovered ? "xb-first" : ""].join(" "),
    sort: {col: "dist", dir: "asc"},
    empty: data.status === "working" ? "Asking Spansh for the bodies…" : "No bodies known here yet: honk the FSS.",
  });
  if (legend) {
    const legendHtml = legendMarkup(data.legend);
    if (legend._html !== legendHtml) {
      legend._html = legendHtml;
      legend.innerHTML = legendHtml;
    }
  }
  pane._xbData = data;
  if (!pane.dataset.xbBound) {
    pane.dataset.xbBound = "1";
    pane.addEventListener("click", (event) => {
      const modeButton = event.target.closest("[data-xb-mode]");
      if (modeButton) {
        if (modeButton.dataset.xbMode === "schematic") {
          ui.setView?.("map");
          return;
        }
        setPref(profile, `${id}.mode`, modeButton.dataset.xbMode);
        renderBodies(pane, pane._xbData, ui, {profile, id, onRow});
        return;
      }
      if (event.target.closest("[data-xb-csv]")) {
        const current = pane._xbData || {};
        const rows = visibleRows(box);
        const csv = toCsv(["Body", "Class", "Distance (ls)", "Gravity (g)", "Bio signals", "Species", "Geo signals", "Rings",
          "First discovered", "First mapped", "Value now", "Value max"], rows.map((row) => [row.name, row.cls_full || row.cls,
          row.dist_ls ?? "", row.gravity ?? "", row.bio_count, (row.bio || []).map((cell) => `${cell.name}${cell.colour ? ` - ${cell.colour}` : ""} (${cell.state})`).join("; "),
          row.geo_count, (row.rings || []).length, row.first_discovered ? "yes" : "", row.first_mapped ? "yes" : "", row.value_now, row.value_max]));
        downloadText(`${current.system || "system"}.csv`, csv);
        return;
      }
      const bookmark = event.target.closest("[data-explore-bookmark]");
      if (bookmark) {
        ui.command?.("workspace", {page: "explore", operation: "bookmark", name: bookmark.dataset.exploreBookmark});
        return;
      }
      const row = event.target.closest("tr[data-xt-key]");
      if (row && onRow) {
        const found = (pane._xbData?.rows || []).find((item) => item.key === row.dataset.xtKey);
        if (found) onRow(found, pane._xbData);
      }
    });
  }
}

export async function loadSystem(ui, name, id64) {
  return fetchData(ui, "explore-system", {name, id64});
}
