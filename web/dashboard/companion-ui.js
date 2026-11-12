import {SIGNATURES} from "../assets/companion-colours.js";

export const COMPANIONS = {
  watcher: {name:"The Watcher",role:"Journal companion",description:"Patient company · an ancient eye"},
  aster: {name:"Aster",role:"Manifest officer",description:"Ship’s officer · precision and dry wit"},
  axiom: {name:"Axiom",role:"Survey intelligence",description:"Survey intelligence · precise and curious"},
  meridian: {name:"Meridian",role:"Veteran navigator",description:"Old navigator · measured and steady"},
  lyra: {name:"Lyra",role:"Ship's computer",description:"A ship's computer · bright, exact and fond of full tanks"},
};
export function companionInfo(source = {}) {
  const selected = source.identity || source.companion_identity;
  const identity = Object.hasOwn(COMPANIONS, selected) ? selected : "watcher";
  return {identity, ...COMPANIONS[identity]};
}

export function renderCompanionChrome(source = {}) {
  const {identity, name} = companionInfo(source);
  if (document.body.dataset.companion === identity) return;
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
  return options;
}

// The companion page's SETUP tab: this companion's colours and what its idle motion looks like.
export function renderCompanionDisplay(panel, source = {}) {
  const {identity} = companionInfo(source);
  const aster = identity !== "watcher";
  const options = source;
  const accent = panel.querySelector('[data-watcher-setting="companion_accent"]');
  if (accent && accent.dataset.identity !== identity) {
    accent.dataset.identity = identity;
    accent.replaceChildren(...[[identity === "watcher" ? "hal" : "signature", SIGNATURES[identity].label],
      ["theme","Theme accent"],["cyan","Ice cyan"],["brass","Brass"]].map(([value, title]) => {
      const option = document.createElement("option"); option.value = value; option.textContent = title; return option;
    }));
  }
  const note = panel.querySelector("[data-companion-motion-note]");
  if (note) note.textContent = identity === "axiom" ? "A ceramic android, camera shutters and active temple processors. Off, it still reacts when addressed." : identity === "meridian" ? "A brass navigator, calm optical shutters and moving compass instruments. Off, it still reacts when addressed." : identity === "lyra" ? "A turning halo, blinking optics and a face that follows her mood. Off, she still reacts when addressed." : aster ? "A command android, expressive visor shutters and moving instrument ring. Off, it still reacts when addressed." : "Aperture, breathing and glances between events; off, it only reacts.";
  if (note && options.companion_motion && (document.body.classList.contains("reduced-motion") || window.matchMedia("(prefers-reduced-motion: reduce)").matches)) note.textContent += " Reduced motion is currently on, so continuous animation is paused.";
  if (note && identity === "lyra") note.textContent = "Blinking optics, gentle head movement, antenna motion, a pulsing chest light, a jaw that moves with her voice, and expressions that follow what she says." + (options.companion_motion && (document.body.classList.contains("reduced-motion") || window.matchMedia("(prefers-reduced-motion: reduce)").matches) ? " Reduced motion is currently on, so continuous animation is paused." : "");
}
