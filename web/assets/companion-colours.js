// Shared by the Studio picker, deck and floating displays. Signature presets
// include both the main light and its highlights, not just a renamed swatch.
export const SIGNATURES = {
  watcher: {label:"HAL red",primary:"#ff4455",secondary:"#ffb1a3"},
  aster: {label:"Aster cyan",primary:"#65e4ef",secondary:"#a8b4ff"},
  axiom: {label:"Axiom violet",primary:"#a897ff",secondary:"#65e4ef"},
  meridian: {label:"Meridian gold",primary:"#e8c48c",secondary:"#74bbff"},
  lyra: {label:"Lyra aurora",primary:"#74ddff",secondary:"#ec9fdb"},
};

export function companionColours(identity, accent, theme) {
  const signature = SIGNATURES[identity] || SIGNATURES.watcher;
  if (accent === "signature" || (identity !== "watcher" && (!accent || accent === "hal"))) return {...signature};
  const primary = {cyan:"#65e4ef",brass:"#e8c48c",hal:"#ff4455"}[accent]
    || (/^#[a-f0-9]{6}$/i.test(theme || "") ? theme : "#65e4ef");
  return {...signature,primary};
}

window.CompanionColours = {SIGNATURES, resolve:companionColours};
window.dispatchEvent(new Event("companion-colours-ready"));
