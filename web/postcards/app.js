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
    block.append(node("span", "greeting-from", "GREETINGS FROM"));
    block.append(node("strong", "greeting-place", card.title || ""));
    const under = [card.place, card.region].filter(Boolean).join(" · ");
    if (under) block.append(node("span", "greeting-region", under));
    return block;
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
    caption.append(greeting(card));
    // The Watcher's note, handwritten and signed; without one, what you
    // were doing, in the same hand.
    if (card.note) {
      const note = node("p", "note", card.note);
      note.append(node("span", "signed", "the Watcher"));
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

  function render(snapshot = {}) {
    const effects = snapshot.effects || {};
    window.VoidCompassOverlay.applyTheme(root, snapshot.theme || {}, effects);
    const model = snapshot.postcards || {};
    const cards = Array.isArray(model.cards) ? model.cards : [];
    const options = model.options || {};
    const width = {small: 280, standard: 340, large: 420}[options.size] || 340;
    document.documentElement.style.setProperty("--card-w", `${width}px`);
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
      element.dataset.style = ["airmail", "holo", "vintage"].includes(options.style) ? options.style : "polaroid";
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
