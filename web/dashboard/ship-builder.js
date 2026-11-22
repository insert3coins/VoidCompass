// The Ship Builder page (5.8.5): the ship builder on a deck page of its own. The builder itself is
// materials-ship.js; this binds it to the page and fetches the engineering tables it names
// blueprints and materials from.
import {renderShipBuilder, handleShipClick, handleShipChange, handleShipSubmit, shipBuilderReset} from "./materials-ship.js";

let ref = null;
let refState = "idle";
let last = {};
let lastUi = null;
let bound = null;

function loadRef(ui) {
  if (refState !== "idle") return;
  refState = "loading";
  fetch(ui.apiUrl("/api/data/materials-reference"), {cache: "no-store"})
    .then((response) => { if (!response.ok) throw new Error(`HTTP ${response.status}`); return response.json(); })
    .then((data) => { ref = data; refState = "ready"; renderShipBuilderPage(last, lastUi, true); })
    .catch(() => { refState = "idle"; });
}

function bind(root) {
  if (bound === root) return;
  bound = root;
  root.addEventListener("click", (event) => handleShipClick(event, lastUi, last, ref));
  root.addEventListener("input", (event) => {
    const ds = event.target.dataset || {};
    if ("msFilter" in ds || "msName" in ds) handleShipChange(event, lastUi, last, ref);
  });
  root.addEventListener("change", (event) => handleShipChange(event, lastUi, last, ref));
  root.addEventListener("submit", (event) => handleShipSubmit(event, lastUi));
}

export function renderShipBuilderPage(data, ui, fresh = false) {
  const root = ui?.byId("ship-builder-workspace");
  if (!root) return;
  last = data || {};
  lastUi = ui;
  bind(root);
  loadRef(ui);
  root.classList.remove("loading-panel");
  let host = root.querySelector("#mt-ship-builder");
  if (!host) {
    root.innerHTML = `<div id="mt-ship-builder" class="mt-ship"></div>`;
    host = root.querySelector("#mt-ship-builder");
    fresh = true;
  }
  renderShipBuilder(host, last, ref, ui, fresh);
}

export function resetShipBuilderPage() {
  shipBuilderReset();
  last = {};
  const root = lastUi?.byId("ship-builder-workspace");
  if (root) root.innerHTML = "";
}
