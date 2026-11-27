// Overlay groups (5.8.1): made in Overlay Studio's GROUPS card, switched from
// there, from the top of the header's PANELS menu, by their hotkeys and the
// Local API. "Only this group" hides every other overlay while it's on; "Add
// these" just shows its overlays while on and hides them while off. A group
// tied to an activity comes on by itself while you're doing it.

let editing = null;          // the group being edited: its id, or "new"
let draft = null;            // the editor's values
let confirmDelete = {id: "", until: 0};

const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[char]));

function groupsOf(studio) {
  const data = studio.groups || {};
  return {groups: Array.isArray(data.groups) ? data.groups : [], activities: data.activities || [], max: Number(data.max) || 8,
    keys: data.keys || {}, activity: data.activity || ""};
}

function activityLabel(data, key) {
  return (data.activities.find(([id]) => id === key) || [key, key])[1];
}

function editor(studio, data) {
  const overlays = (Array.isArray(studio.overlays) ? studio.overlays : []).slice().sort((a, b) => String(a.label).localeCompare(String(b.label)));
  const members = new Set(draft.members || []);
  const boxes = overlays.map((row) => `<label class="og-member${members.has(row.id) ? " on" : ""}"><input type="checkbox" name="members" value="${esc(row.id)}"${members.has(row.id) ? " checked" : ""}>
      <span>${esc(row.label)}</span>${row.enabled ? "" : "<small>OFF</small>"}</label>`).join("");
  const activities = data.activities.map(([id, label]) => `<option value="${esc(id)}"${id === (draft.activity || "") ? " selected" : ""}>${esc(label)}</option>`).join("");
  return `<form class="og-editor" data-og-form>
      <div class="og-editor-row">
        <label class="studio-field"><span>Name</span><input name="name" value="${esc(draft.name || "")}" maxlength="40" placeholder="Rhino, Exploring, Combat…" required></label>
        <label class="studio-field"><span>Type<small>What happens to the other overlays</small></span><select name="mode">
          <option value="only"${draft.mode === "only" ? " selected" : ""}>Only this group: the rest hide</option>
          <option value="add"${draft.mode !== "only" ? " selected" : ""}>Add these: the rest stay as they are</option></select></label>
        <label class="studio-field"><span>Comes on by itself<small>While you're doing this</small></span><select name="activity">${activities}</select></label>
      </div>
      <p class="og-hint">Its overlays (one that's off is turned on when the group comes on):</p>
      <div class="og-members">${boxes}</div>
      <div class="og-actions"><button type="submit" class="primary">SAVE GROUP</button><button type="button" data-og-op="cancel">CANCEL</button></div>
    </form>`;
}

// The GROUPS card in Overlay Studio.
export function renderOverlayGroups(studio) {
  const host = document.getElementById("studio-groups");
  if (!host) return;
  if (host.contains(document.activeElement) && document.activeElement.closest("[data-og-form]")) return;
  const data = groupsOf(studio);
  const rows = data.groups.map((group) => {
    const key = data.keys[group.slot] ? `<kbd>${esc(data.keys[group.slot])}</kbd>` : `<small>no key</small>`;
    const armed = confirmDelete.id === group.id && Date.now() < confirmDelete.until;
    return `<li class="og-row${group.on ? " on" : ""}">
      <button type="button" class="og-switch" data-og-op="toggle" data-id="${esc(group.id)}" aria-pressed="${group.on}" title="${group.on ? "On: click to switch it off" : "Off: click to switch it on"}"><i></i><b>${group.on ? "ON" : "OFF"}</b></button>
      <span class="og-name"><b>${esc(group.name)}</b><small>${group.mode === "only" ? "ONLY THIS GROUP" : "ADDS ITS OVERLAYS"} · ${group.members.length} overlay${group.members.length === 1 ? "" : "s"}${group.activity ? ` · ${esc(activityLabel(data, group.activity))}${group.auto ? " (now)" : ""}` : ""}</small></span>
      <span class="og-key">GROUP ${group.slot} ${key}</span>
      <span class="og-tools"><button type="button" data-og-op="up" data-id="${esc(group.id)}" title="Up the list (its place is its hotkey)">▲</button><button type="button" data-og-op="down" data-id="${esc(group.id)}" title="Down the list">▼</button>
        <button type="button" data-og-op="edit" data-id="${esc(group.id)}">EDIT</button><button type="button" class="og-danger${armed ? " armed" : ""}" data-og-op="delete" data-id="${esc(group.id)}">${armed ? "SURE?" : "DELETE"}</button></span>
    </li>`;
  }).join("");
  const room = data.groups.length < data.max;
  const markup = `<header><span>OVERLAY GROUPS</span><b>${data.groups.length} OF ${data.max}</b></header>
    <div class="og-body">
      <p class="og-hint">Groups of overlays for whatever you're doing. Switch one from here, from the top of PANELS in the header, by its hotkey (Settings › Helm › Shortcuts › Controls: Group 1 to ${data.max}, by its place here) or the Local API.</p>
      ${data.groups.length ? `<ul class="og-list">${rows}</ul>` : `<p class="og-empty">No groups yet. Make one for the Rhino, say, with the Rig Tracker and the Rhino Map, set to come on by itself in the Rhino.</p>`}
      ${editing ? editor(studio, data) : room ? `<button type="button" class="og-new" data-og-op="new">+ NEW GROUP</button>` : ""}
    </div>`;
  if (host.dataset.markup === markup) return;
  host.dataset.markup = markup;
  host.innerHTML = markup;
}

// The inspector's row (5.8.3): the groups the selected overlay is in, each a
// switch to put it in or take it out.
export function renderGroupMembership(studio, overlayId) {
  const host = document.getElementById("studio-selected-groups");
  if (!host) return;
  const data = groupsOf(studio);
  const chips = data.groups.map((group) => {
    const member = group.members.includes(overlayId);
    return `<button type="button" class="og-member-chip${member ? " on" : ""}" data-og-member="${esc(group.id)}" aria-pressed="${member}" title="${member ? `In ${esc(group.name)}: click to take it out` : `Put it in ${esc(group.name)}`}"><i></i>${esc(group.name)}</button>`;
  }).join("");
  const markup = overlayId ? `<small>IN GROUPS</small>${chips || `<span>None yet: make one under OVERLAY GROUPS.</span>`}` : "";
  if (host.dataset.markup === markup && host.dataset.overlay === overlayId) return;
  host.dataset.markup = markup;
  host.dataset.overlay = overlayId || "";
  host.innerHTML = markup;
}

// The group buttons at the top of the header's PANELS menu.
export function groupChips(studio) {
  const data = groupsOf(studio);
  if (!data.groups.length) return [];
  const label = document.createElement("small");
  label.className = "og-quick-label";
  label.textContent = "GROUPS";
  const chips = data.groups.map((group) => {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.overlayGroup = group.id;
    button.className = `og-quick${group.on ? " on" : ""}`;
    button.setAttribute("aria-pressed", String(Boolean(group.on)));
    button.title = `${group.name}: ${group.mode === "only" ? "only these overlays" : "adds its overlays"}. ${group.on ? "On: click to switch it off" : "Off: click to switch it on"}`;
    button.append(document.createElement("i"));
    const name = document.createElement("span");
    name.textContent = group.name;
    button.append(name);
    return button;
  });
  const rule = document.createElement("hr");
  rule.className = "og-quick-rule";
  return [label, ...chips, rule];
}

export function groupChipsFingerprint(studio) {
  return JSON.stringify(groupsOf(studio).groups.map((group) => [group.id, group.name, group.on, group.mode]));
}

export async function handleOverlayGroupsClick(event, ui, studio) {
  const chip = event.target.closest?.("#studio-selected-groups [data-og-member]");
  if (chip) {
    const host = chip.closest("#studio-selected-groups");
    const member = chip.getAttribute("aria-pressed") !== "true";
    chip.setAttribute("aria-pressed", String(member));
    chip.classList.toggle("on", member);
    await ui.command("overlay_studio", {operation: "group_member", group_id: chip.dataset.ogMember,
      overlay_id: host?.dataset.overlay || "", member});
    return true;
  }
  const quick = event.target.closest?.("[data-overlay-group]");
  if (quick) {
    await ui.command("overlay_studio", {operation: "group_toggle", group_id: quick.dataset.overlayGroup});
    return true;
  }
  const control = event.target.closest?.("#studio-groups [data-og-op]");
  if (!control) return false;
  const op = control.dataset.ogOp, id = control.dataset.id;
  const groups = groupsOf(studio).groups;
  if (op === "new") { editing = "new"; draft = {name: "", mode: "add", activity: "", members: []}; }
  else if (op === "edit") { const group = groups.find((row) => row.id === id); editing = id; draft = group ? {...group, members: [...group.members]} : null; }
  else if (op === "cancel") { editing = null; draft = null; }
  else if (op === "toggle") await ui.command("overlay_studio", {operation: "group_toggle", group_id: id});
  else if (op === "up" || op === "down") await ui.command("overlay_studio", {operation: "group_move", group_id: id, step: op === "up" ? -1 : 1});
  else if (op === "delete") {
    if (confirmDelete.id !== id || Date.now() > confirmDelete.until) {
      confirmDelete = {id, until: Date.now() + 4000};
    } else {
      confirmDelete = {id: "", until: 0};
      if (editing === id) { editing = null; draft = null; }
      await ui.command("overlay_studio", {operation: "group_delete", group_id: id});
    }
  }
  const host = document.getElementById("studio-groups");
  if (host) delete host.dataset.markup;
  renderOverlayGroups(studio);
  return true;
}

// The editor's ticks are kept as they change, so a redraw never loses them.
export function handleOverlayGroupsInput(event) {
  const form = event.target.closest?.("[data-og-form]");
  if (!form || !draft) return false;
  draft = {...draft, ...readForm(form)};
  event.target.closest(".og-member")?.classList.toggle("on", Boolean(event.target.checked));
  return true;
}

function readForm(form) {
  return {name: form.elements.name.value.trim(), mode: form.elements.mode.value, activity: form.elements.activity.value,
    members: [...form.querySelectorAll('input[name="members"]:checked')].map((input) => input.value)};
}

export async function handleOverlayGroupsSubmit(event, ui, studio) {
  const form = event.target.closest?.("[data-og-form]");
  if (!form) return false;
  event.preventDefault();
  const values = readForm(form);
  if (!values.name) return true;
  const accepted = await ui.command("overlay_studio", {operation: "group_save", group: {...values, id: editing === "new" ? "" : editing}});
  if (accepted !== false) { editing = null; draft = null; }
  document.activeElement?.blur?.();
  const host = document.getElementById("studio-groups");
  if (host) delete host.dataset.markup;
  renderOverlayGroups(studio);
  return true;
}
