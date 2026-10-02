/* Text size and smallest text (Settings > Appearance > Display).

   The deck sizes its text in px: about a thousand rules, most of them small
   7 to 10 px labels. Once, at start, every px font-size in the deck's own
   stylesheets becomes

     max(size × var(--text-scale), var(--text-min))

   so one change to two custom properties resizes all of it: --text-scale
   grows every text in proportion, and --text-min lifts only the text
   smaller than it, leaving headings where they are. Layout widths stay as
   designed; line heights are unitless and follow. Canvas drawings (the
   orrery, the boot galaxy) and the atlas frame are not text rules and keep
   their sizes; Command deck scale zooms those along with everything. */

const PX = /^(\d*\.?\d+)px$/;
// The logo lockup is branding sized to the fixed top bar, not reading text.
const FIXED = /^\.brand(?![\w-])/;
let prepared = false;

function rewrite(rules) {
  for (const rule of rules) {
    // @media, @container, @supports and @layer blocks hold rules of their own.
    if (rule.cssRules && !rule.style) {
      rewrite(rule.cssRules);
      continue;
    }
    const style = rule.style;
    if (!style || FIXED.test(rule.selectorText || "")) continue;
    const match = PX.exec(style.getPropertyValue("font-size").trim());
    if (!match) continue;
    style.setProperty("font-size", `max(calc(${match[1]}px * var(--text-scale, 1)), var(--text-min, 0px))`,
      style.getPropertyPriority("font-size"));
  }
}

function prepare() {
  for (const sheet of document.styleSheets) {
    try {
      rewrite(sheet.cssRules);
    } catch (_error) {
      // A sheet from another origin can't be read; the deck has none.
    }
  }
  prepared = true;
}

export function applyTextSize(scalePercent, minimumPx) {
  const scale = Math.max(0.8, Math.min(2, (Number(scalePercent) || 100) / 100));
  const minimum = Math.max(0, Math.min(18, Number(minimumPx) || 0));
  const root = document.documentElement.style;
  const next = `${scale}|${minimum}`;
  if (root.getPropertyValue("--text-size-applied") === next) return;
  // Standard sizes need no rewrite; the first change from them does it.
  if (!prepared && (scale !== 1 || minimum > 0)) prepare();
  root.setProperty("--text-scale", String(scale));
  root.setProperty("--text-min", `${minimum}px`);
  root.setProperty("--text-size-applied", next);
}
