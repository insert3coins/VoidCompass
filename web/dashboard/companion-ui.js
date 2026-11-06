import {SIGNATURES} from "../assets/companion-colours.js";

export const COMPANIONS = {
  watcher: {name:"The Watcher",role:"Journal companion",description:"Patient company · an ancient eye"},
  aster: {name:"Aster",role:"Manifest officer",description:"Ship’s officer · precision and dry wit"},
  axiom: {name:"Axiom",role:"Survey intelligence",description:"Survey intelligence · precise and curious"},
  meridian: {name:"Meridian",role:"Veteran navigator",description:"Old navigator · measured and steady"},
  lyra: {name:"Lyra",role:"Robot companion",description:"Pearl shell · cyan optics · overlay preview",overlay_only:true},
};
export function companionInfo(source = {}) {
  const selected = source.identity || source.companion_identity;
  const identity = Object.hasOwn(COMPANIONS, selected) ? selected : "watcher";
  return {identity, ...COMPANIONS[identity]};
}

export function renderCompanionChrome(source = {}) {
  const {identity, name} = companionInfo(source);
  document.body.dataset.companion = identity;
  const nav = document.querySelector('.nav-item[data-page="watcher"]');
  if (nav) {
    nav.querySelector("span").textContent = name;
    nav.setAttribute("aria-label", name);
    nav.title = `${name}: replies, story and companion settings`;
    if (nav.querySelector("i")) nav.querySelector("i").textContent = {watcher:"◉",aster:"⬡",axiom:"◌",meridian:"◇",lyra:"✧"}[identity];
  }
  const heading = document.querySelector('[data-page-name="watcher"] .page-title h2');
  if (heading) heading.textContent = name;
  document.querySelectorAll("[data-companion-name]").forEach(node => { node.textContent = name; });
}

export function renderCompanionStudio(source = {}) {
  const {identity, name} = companionInfo(source);
  const aster = identity !== "watcher";
  const options = {...source,
    companion_size: source.companion_size ?? (aster ? source[`${identity}_hud_size`] ?? 144 : source.heartbeat_orb_size ?? 54),
    companion_accent: source.companion_accent ?? (aster ? source[`${identity}_hud_accent`] ?? "signature" : source.heartbeat_eye_color ?? "theme"),
    companion_motion: source.companion_motion ?? (aster ? source[`${identity}_hud_motion`] !== false : source.heartbeat_idle_motion !== false),
    companion_focus: source.companion_focus ?? (aster ? source[`${identity}_hud_focus`] ?? "tracking" : source.heartbeat_focus_movement ?? "tracking"),
    companion_liveliness: source.companion_liveliness ?? (aster ? source[`${identity}_hud_liveliness`] ?? "standard" : source.heartbeat_liveliness ?? "standard"),
  };
  if (aster && options.companion_accent === "hal") options.companion_accent = "signature";
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
  choices("companion_accent", [[identity === "watcher" ? "hal" : "signature",SIGNATURES[identity].label],
    ["theme","Theme accent"],["cyan","Ice cyan"],["brass","Brass"]]);
  choices("companion_focus", [["off","Fixed focus"],["tracking","Tracking"],["expressive","Expressive"]]);
  choices("companion_liveliness", [["calm","Calm"],["standard","Standard"],["alive","Lively"]]);
  const note = panel.querySelector("[data-companion-motion-note]");
  if (note) note.textContent = identity === "axiom" ? "Flowing particles, breathing ripples and counter-rotating light trails. Off, it still reacts when addressed." : identity === "meridian" ? "Turning instrument rings, a moving scan band and gentle portrait movement. Off, it still reacts when addressed." : aster ? "A flowing light halo and animated command core. Off, it still reacts when addressed." : "Aperture, breathing and glances between events; off, it only reacts.";
  if (note && options.companion_motion && (document.body.classList.contains("reduced-motion") || window.matchMedia("(prefers-reduced-motion: reduce)").matches)) note.textContent += " Reduced motion is currently on, so continuous animation is paused.";
  if (note && identity === "lyra") note.textContent = "Blinking optics, gentle head movement, antenna motion and a pulsing chest light. Voice and story are pending." + (options.companion_motion && (document.body.classList.contains("reduced-motion") || window.matchMedia("(prefers-reduced-motion: reduce)").matches) ? " Reduced motion is currently on, so continuous animation is paused." : "");
  return options;
}
