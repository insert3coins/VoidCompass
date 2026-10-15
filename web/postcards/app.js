// Postcards (5.5.3.7): a screenshot taken in game, as a Polaroid. Cards are
// kept by id between snapshots, so a card slides in once and its picture
// develops once, however often the model is published.
(() => {
  "use strict";
  const params = new URLSearchParams(location.search);
  const token = params.get("token") || "";
  const overlay = params.get("overlay") || "postcards";
  const root = document.getElementById("postcards");
  const shown = new Map();

  function node(tag, className = "", text = "") {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== "") element.textContent = String(text);
    return element;
  }

  function photoUrl(card) {
    return `/api/file?token=${encodeURIComponent(token)}&overlay=${encodeURIComponent(overlay)}&name=photo-${encodeURIComponent(card.id)}`;
  }

  // "Greetings from…", as old travel postcards say it: the place in big
  // slanted letters, the region under it. On the photo, or on the paper
  // when there's no photo.
  function greeting(card) {
    const block = node("div", "greeting");
    // The lettering over the name (5.5.3.8): the card's own words, or none.
    const words = String(card.greeting ?? "Greetings from").trim();
    if (words) block.append(node("span", "greeting-from", words.toUpperCase()));
    block.append(node("strong", "greeting-place", card.title || ""));
    const under = [card.place, card.region].filter(Boolean).join(" · ");
    if (under) block.append(node("span", "greeting-region", under));
    return block;
  }

  // A postmark (5.5.4): the system round the top, the date underneath, the
  // time in the middle, and the wavy cancellation, as saved postcards have.
  const SVG = "http://www.w3.org/2000/svg";
  function svg(tag, attrs, text = "") {
    const element = document.createElementNS(SVG, tag);
    for (const [name, value] of Object.entries(attrs)) element.setAttribute(name, value);
    if (text) element.textContent = text;
    return element;
  }
  function postmark(card) {
    const key = String(card.id).replace(/[^\w-]/g, "");
    const mark = svg("svg", {class: "postmark", viewBox: "0 0 124 100", "aria-hidden": "true"});
    mark.append(
      svg("path", {id: `pm-top-${key}`, d: "M 45,50 A 29,29 0 0 1 103,50", fill: "none"}),
      svg("path", {id: `pm-bottom-${key}`, d: "M 38,50 A 36,36 0 0 0 110,50", fill: "none"}),
      svg("circle", {cx: 74, cy: 50, r: 44, fill: "none", stroke: "currentColor", "stroke-width": 2.4}),
      svg("circle", {cx: 74, cy: 50, r: 25, fill: "none", stroke: "currentColor", "stroke-width": 1.4}));
    for (const row of [0, 1, 2, 3]) {
      const y = 34 + row * 11;
      mark.append(svg("path", {d: `M 0,${y} q 5,-4 10,0 t 10,0 t 10,0`, fill: "none", stroke: "currentColor", "stroke-width": 2}));
    }
    const arc = (id, words) => {
      const text = svg("text", {class: "postmark-arc"});
      text.append(svg("textPath", {href: `#${id}`, startOffset: "50%", "text-anchor": "middle"}, words));
      return text;
    };
    const place = String(card.place || card.title || "").toUpperCase();
    mark.append(arc(`pm-top-${key}`, place.length > 18 ? `${place.slice(0, 17)}…` : place),
      arc(`pm-bottom-${key}`, String(card.date || "").toUpperCase()),
      svg("text", {class: "postmark-time", x: 74, y: 55, "text-anchor": "middle"}, card.time || ""));
    return mark;
  }

  // The place's name, as big as fits.
  function fitPlace(element) {
    for (const place of element.querySelectorAll(".greeting-place")) {
      place.style.removeProperty("font-size");
      let size = parseFloat(getComputedStyle(place).fontSize) || 30;
      while (place.scrollWidth > place.clientWidth + 1 && size > 13) {
        size -= 1;
        place.style.fontSize = `${size}px`;
      }
    }
  }

  function build(card) {
    const element = node("article", "card");
    element.dataset.id = card.id;
    const photo = node("div", "photo");
    photo.append(node("span", "waiting", "DEVELOPING…"));
    if (card.high_res) photo.append(node("span", "badge", "HIGH RES"));
    photo.append(greeting(card));
    const caption = node("div", "caption");
    caption.append(greeting(card), postmark(card));
    // The Watcher's note, handwritten and signed; without one, what you
    // were doing, in the same hand.
    if (card.note) {
      const note = node("p", "note", card.note);
      // Your own words are signed as you (5.5.4).
      note.append(node("span", "signed", card.signed || "the Watcher"));
      caption.append(note);
    } else if (card.doing) {
      caption.append(node("p", "note plain", card.doing));
    }
    // What the journal knows of the place.
    if (Array.isArray(card.facts) && card.facts.length) {
      const facts = node("div", "facts");
      for (const fact of card.facts) facts.append(node("span", "", fact));
      caption.append(facts);
    }
    const where = [card.note ? card.doing : "", card.coordinates].filter(Boolean).join(" · ");
    if (where) caption.append(node("span", "coords", where));
    const when = node("div", "when");
    when.append(node("span", "", card.date || ""), node("span", "", card.time || ""));
    caption.append(when);
    element.append(photo, caption);
    return element;
  }

  // The picture, once Void Compass has read it: it develops in.
  function develop(element, card) {
    const photo = element.querySelector(".photo");
    if (!card.photo || photo.querySelector("img")) return;
    const image = new Image();
    image.alt = "";
    image.addEventListener("load", () => {
      photo.querySelector(".waiting")?.remove();
      image.classList.add("developing");
      photo.prepend(image);
    }, {once: true});
    image.src = photoUrl(card);
  }

  // Your own theme (5.5.4): colours, lettering, photo filter and angle as
  // custom properties on the card; the background behind the stack.
  const FONTS = {hud: '"Bahnschrift SemiCondensed", "Bahnschrift", sans-serif', serif: 'Georgia, "Times New Roman", serif',
    hand: '"Segoe Print", "Ink Free", cursive'};
  function applyTheme(element, theme) {
    for (const name of ["--paper", "--ink", "--ink-soft", "--greet", "--font-greet", "--tilt"]) element.style.removeProperty(name);
    element.dataset.filter = "";
    element.dataset.font = "";
    if (!theme) return;
    if (theme.paper) element.style.setProperty("--paper", theme.paper);
    if (theme.ink) element.style.setProperty("--ink", theme.ink);
    if (theme.paper || theme.ink) element.style.setProperty("--ink-soft", "color-mix(in srgb, var(--ink) 62%, var(--paper))");
    if (theme.greet) element.style.setProperty("--greet", theme.greet);
    if (theme.font) {
      element.style.setProperty("--font-greet", FONTS[theme.font] || FONTS.hud);
      element.dataset.font = theme.font;
    }
    if (theme.angle !== null && theme.angle !== undefined) element.style.setProperty("--tilt", `${Number(theme.angle)}deg`);
    element.dataset.filter = theme.filter && theme.filter !== "none" ? theme.filter : "";
  }

  function backdrop(theme) {
    root.style.removeProperty("--backdrop");
    root.classList.toggle("backdrop", Boolean(theme && ["colour", "image"].includes(theme.background)));
    if (!theme) return;
    if (theme.background === "colour" && theme.bg_colour) root.style.setProperty("--backdrop", theme.bg_colour);
    if (theme.background === "image" && theme.bg_image) {
      root.style.setProperty("--backdrop", `center / cover no-repeat url("/api/file?token=${encodeURIComponent(token)}&overlay=${encodeURIComponent(overlay)}&name=theme-bg&v=${encodeURIComponent(theme.bg_image)}")`);
    }
  }

  function render(snapshot = {}) {
    const effects = snapshot.effects || {};
    window.VoidCompassOverlay.applyTheme(root, snapshot.theme || {}, effects);
    const model = snapshot.postcards || {};
    const cards = Array.isArray(model.cards) ? model.cards : [];
    const options = model.options || {};
    const width = {small: 280, standard: 340, large: 420}[options.size] || 340;
    document.documentElement.style.setProperty("--card-w", `${width}px`);
    backdrop(options.theme);
    root.classList.toggle("empty", !cards.length);
    const ids = new Set(cards.map((card) => card.id));
    for (const [id, element] of shown) {
      if (!ids.has(id)) { element.remove(); shown.delete(id); }
    }
    cards.forEach((card, index) => {
      let element = shown.get(card.id);
      if (!element) {
        element = build(card);
        shown.set(card.id, element);
      }
      element.classList.toggle("top", index === 0);
      element.classList.toggle("behind", index > 0);
      element.classList.toggle("no-photo", options.photo === false);
      element.classList.toggle("postmarked", options.postmark !== false);
      element.dataset.style = ["airmail", "holo", "vintage"].includes(options.style) ? options.style : "polaroid";
      applyTheme(element, options.theme);
      if (options.photo !== false) develop(element, card);
      fitPlace(element);
      // Newest first. Only a card out of place is moved (moving one would
      // play its arrival again).
      if (root.children[index] !== element) root.insertBefore(element, root.children[index] || null);
    });
    root.setAttribute("aria-label", cards.length ? `Postcard: ${cards[0].title}` : "Postcards");
  }

  // The height the cards need: the stack plus its margins.
  function contentHeight() {
    const box = root.getBoundingClientRect();
    return Math.ceil(box.bottom + 18 * (Number(getComputedStyle(document.documentElement).getPropertyValue("--scale")) || 1));
  }

  window.__postcards = {shown: () => [...shown.keys()]};
  window.VoidCompassOverlay.startPolling({token, overlay, render, contentHeight, interval: 250});
})();
