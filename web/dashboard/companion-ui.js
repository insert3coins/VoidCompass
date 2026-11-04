const names = {watcher: "The Watcher", aster: "Aster"};
export function companionInfo(source = {}) {
  const identity = (source.identity || source.companion_identity) === "aster" ? "aster" : "watcher";
  return {identity, name: names[identity]};
}

export function renderCompanionChrome(source = {}) {
  const {identity, name} = companionInfo(source);
  document.body.dataset.companion = identity;
  const nav = document.querySelector('.nav-item[data-page="watcher"]');
  if (nav) {
    nav.querySelector("span").textContent = name;
    nav.setAttribute("aria-label", name);
    nav.title = `${name}: replies, story and companion settings`;
    if (nav.querySelector("i")) nav.querySelector("i").textContent = identity === "aster" ? "⬡" : "◉";
  }
  const heading = document.querySelector('[data-page-name="watcher"] .page-title h2');
  if (heading) heading.textContent = name;
  document.querySelectorAll("[data-companion-name]").forEach(node => { node.textContent = name; });
}

export function renderCompanionStudio(source = {}) {
  const {identity, name} = companionInfo(source);
  const aster = identity === "aster";
  const options = {...source,
    companion_size: source.companion_size ?? (aster ? source.aster_hud_size ?? 144 : source.heartbeat_orb_size ?? 54),
    companion_accent: source.companion_accent ?? (aster ? source.aster_hud_accent ?? "theme" : source.heartbeat_eye_color ?? "theme"),
    companion_motion: source.companion_motion ?? (aster ? source.aster_hud_motion !== false : source.heartbeat_idle_motion !== false),
    companion_focus: source.companion_focus ?? (aster ? source.aster_hud_focus ?? "tracking" : source.heartbeat_focus_movement ?? "tracking"),
    companion_liveliness: source.companion_liveliness ?? (aster ? source.aster_hud_liveliness ?? "standard" : source.heartbeat_liveliness ?? "standard"),
  };
  const panel = document.querySelector('[data-studio-settings="heartbeat_hud"]');
  if (!panel) return options;
  const changed = panel.dataset.identity !== identity;
  panel.dataset.identity = identity;
  panel.querySelector("h4").textContent = `${name.toUpperCase()} · COMPANION DISPLAY`;
  const choices = (key, values) => {
    const field = panel.querySelector(`[data-studio-setting="${key}"]`);
    if (!field) return;
    if (changed || !field.options.length) field.replaceChildren(...values.map(([value, title]) => {
      const option = document.createElement("option"); option.value = value; option.textContent = title; return option;
    }));
    if (changed || document.activeElement !== field) field.value = String(options[key]);
  };
  choices("companion_size", [54,72,96,144,192,256].map(size => [String(size), `${size} PX`]));
  choices("companion_accent", [["theme","Theme accent"],["cyan","Ice cyan"],["brass","Brass"],["hal","HAL red"]]);
  choices("companion_focus", [["off","Fixed focus"],["tracking","Tracking"],["expressive","Expressive"]]);
  choices("companion_liveliness", [["calm","Calm"],["standard","Standard"],["alive","Lively"]]);
  const note = panel.querySelector("[data-companion-motion-note]");
  if (note) note.textContent = aster ? "A flowing light halo and animated command core. Off, it still reacts when addressed." : "Aperture, breathing and glances between events; off, it only reacts.";
  if (note && options.companion_motion && (document.body.classList.contains("reduced-motion") || window.matchMedia("(prefers-reduced-motion: reduce)").matches)) note.textContent += " Reduced motion is currently on, so continuous animation is paused.";
  return options;
}
