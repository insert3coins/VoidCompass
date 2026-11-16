(() => {
  "use strict";
  // Stream Chat (5.8.3): your companion answering your stream's chat.
  // Two looks (Overlay Studio): a chat box in the Neon styles (Neon rail,
  // Bubbles, Boxed, Clean or Cards in sixteen styles) with viewers' lines,
  // badges and Twitch emotes around the companion's answers; or the Navigation
  // HUD's frame with answer cards. Either way a game shows its prompt, a
  // countdown and the guesses so far, raids, subs, wins and promotions get a
  // banner, and at the end the credits roll.
  const params = new URLSearchParams(location.search);
  const token = params.get("token") || "";
  const overlay = params.get("overlay") || "stream-chat";
  const ids = ["stream", "content", "stream-head", "stream-banner", "stream-game", "stream-cards", "stream-lines", "stream-hint", "stream-credits"];
  const dom = Object.fromEntries(ids.map((id) => [id, document.getElementById(id)]));
  const OFFICERS = ["watcher", "aster", "axiom", "meridian", "lyra"];
  const OFFICER_HUE = {watcher: "#e0574f", aster: "#d9a441", axiom: "#8f9bff", meridian: "#3fbf8f", lyra: "#74ddff"};
  const DESIGN_WIDTH = 420, MIN_HEIGHT = 48;
  const BADGES = {broadcaster: "◆", mod: "⚔", sub: "★"};
  // Twitch's roles as coloured initials, when there's no badge picture.
  const ROLE_BADGES = {broadcaster: ["B", "#E91916"], moderator: ["M", "#00AD03"], vip: ["V", "#E005B9"],
    subscriber: ["S", "#8205B4"], founder: ["F", "#8205B4"]};
  const EVENT_ROWS = {raid: ["🚀", "#FFC53D"], sub: ["★", "#9B5CFF"], gift: ["🎁", "#FF2BD6"], bits: ["💎", "#00F0FF"]};
  const NAME_PALETTE = ["#00F0FF", "#FF2BD6", "#9B5CFF", "#39FF88", "#FFC53D", "#FF7A45", "#4DA3FF", "#FF4D6D"];
  // The card styles: variant, icon shape, font, radius and colours.
  const CARDS = {
    synthwave: ["neon", "Trebuchet MS", 12, ["#ff53d8", "#5be7ff", "#ffeefe", "#f5a8ff", "rgba(24,8,36,.88)", "rgba(42,16,60,.72)", "rgba(91,231,255,.45)", "rgba(255,83,216,.25)"]],
    cybernetik: ["tech", "Share Tech Mono", 8, ["#00f0ff", "#ff2d95", "#e8fdff", "#7feaff", "rgba(7,18,28,.9)", "rgba(8,34,46,.72)", "rgba(0,240,255,.42)", "rgba(0,240,255,.24)"]],
    glitch2: ["glitch", "Share Tech Mono", 6, ["#7aff00", "#ff005d", "#f7fff4", "#b6ff8c", "rgba(9,11,13,.92)", "rgba(31,14,24,.78)", "rgba(122,255,0,.35)", "rgba(255,0,93,.22)"]],
    iridescent: ["glass", "Segoe UI", 16, ["#9af7ff", "#ff9adf", "#ffffff", "#dce9ff", "rgba(32,28,56,.62)", "rgba(73,55,99,.46)", "rgba(255,255,255,.25)", "rgba(154,247,255,.18)"]],
    clearview: ["minimal", "Verdana", 10, ["#6be4ff", "#7d8bff", "#f8fbff", "#c7d8ee", "rgba(11,18,29,.68)", "rgba(17,32,49,.44)", "rgba(107,228,255,.22)", "rgba(0,0,0,.18)"]],
    "bubble-trouble": ["soft", "Trebuchet MS", 20, ["#7de8ff", "#ff9be1", "#ffffff", "#d7f8ff", "rgba(32,59,78,.7)", "rgba(68,129,160,.46)", "rgba(125,232,255,.32)", "rgba(125,232,255,.16)"]],
    "blossom-breeze": ["petal", "Segoe UI", 18, ["#ffb7d8", "#ffd978", "#fffafc", "#ffe1ee", "rgba(74,34,57,.72)", "rgba(129,68,95,.44)", "rgba(255,183,216,.34)", "rgba(255,183,216,.18)"]],
    "snow-blaster": ["frost", "Verdana", 14, ["#b7f0ff", "#79bfff", "#f7fcff", "#d9f4ff", "rgba(13,27,41,.8)", "rgba(46,79,110,.48)", "rgba(183,240,255,.3)", "rgba(121,191,255,.18)"]],
    "cupids-aim": ["romance", "Segoe UI", 18, ["#ff6ba2", "#ffd36e", "#fff7fb", "#ffd5e7", "rgba(61,18,35,.78)", "rgba(111,45,70,.5)", "rgba(255,107,162,.34)", "rgba(255,107,162,.18)"]],
    champion: ["esports", "Trebuchet MS", 6, ["#ffd24f", "#ff5f5f", "#fffdf6", "#ffe9a8", "rgba(20,17,17,.9)", "rgba(63,34,25,.56)", "rgba(255,210,79,.34)", "rgba(255,95,95,.2)"]],
    construct: ["frame", "Share Tech Mono", 8, ["#7df7d7", "#49a8ff", "#effff9", "#b6ffe8", "rgba(10,22,20,.88)", "rgba(18,53,49,.58)", "rgba(125,247,215,.3)", "rgba(73,168,255,.18)"]],
    "electro-junkie": ["grunge", "Share Tech Mono", 6, ["#ffe66a", "#6cff7f", "#fffdea", "#fff4a8", "rgba(26,19,8,.9)", "rgba(61,48,17,.6)", "rgba(255,230,106,.34)", "rgba(108,255,127,.14)"]],
    "sticker-bomb": ["sticker", "Trebuchet MS", 14, ["#00f0ff", "#ffde59", "#ffffff", "#ffeaa1", "rgba(31,20,43,.88)", "rgba(74,42,98,.56)", "rgba(255,222,89,.36)", "rgba(0,240,255,.18)"]],
    "nova-pixel": ["pixel", "Share Tech Mono", 0, ["#7cf7ff", "#ff8ae2", "#f5ffff", "#bafaff", "rgba(13,24,39,.92)", "rgba(23,50,71,.66)", "rgba(124,247,255,.34)", "rgba(255,138,226,.14)"]],
    amused: ["soft", "Segoe UI", 18, ["#ffd166", "#ff7fb8", "#fffaf2", "#ffe4ae", "rgba(31,18,29,.84)", "rgba(77,40,65,.52)", "rgba(255,209,102,.32)", "rgba(255,127,184,.18)"]],
    flow: ["glass", "Segoe UI", 18, ["#7dd3ff", "#8df0c9", "#f9fdff", "#d1eef8", "rgba(28,46,59,.56)", "rgba(78,120,144,.34)", "rgba(125,211,255,.24)", "rgba(0,0,0,.14)"]],
  };
  const CARD_VARS = ["accent", "secondary", "text", "muted", "surface", "soft", "line", "shadow"];
  let creditsKey = "";
  let shownLines = new Set();
  let listKey = "";
  const timerMax = {};

  function node(tag, className = "", text = "") {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== "") element.textContent = String(text);
    return element;
  }
  const validHex = (value) => /^#[0-9a-f]{6}$/i.test(String(value || ""));
  // A viewer's own chat colour, kept readable on the dark frame.
  function chatColour(value) {
    return validHex(value) ? `color-mix(in srgb, ${value} 78%, white)` : "var(--accent)";
  }
  function nameColour(line) {
    if (validHex(line.color)) return line.color;
    let hash = 0;
    for (const ch of line.who || "") hash = (hash * 31 + ch.charCodeAt(0)) | 0;
    return NAME_PALETTE[Math.abs(hash) % NAME_PALETTE.length];
  }

  // -- the look ---------------------------------------------------------------------------
  function applyLook(model) {
    const look = model.look || {};
    const style = look.style || "neon";
    const neon = style !== "hud";
    const root = dom.stream;
    root.classList.toggle("neon", neon);
    for (const name of ["neon", "bubbles", "boxed", "clean", "card"]) root.classList.toggle(`look-${name}`, neon && style === name);
    const officer = OFFICER_HUE[model.identity] || "#00F0FF";
    root.style.setProperty("--who", officer);
    root.style.setProperty("--na", look.accent === "companion" ? officer : (validHex(look.accent) ? look.accent : "#FF2BD6"));
    root.style.setProperty("--box-h", `${Number(look.height) || 480}px`);
    for (const name of Object.values(CARDS).map((card) => card[0])) root.classList.toggle(`v-${name}`, false);
    if (neon && style === "card") {
      const [variant, font, radius, colours] = CARDS[look.card] || CARDS.synthwave;
      root.classList.add(`v-${variant}`);
      CARD_VARS.forEach((name, index) => root.style.setProperty(`--c-${name}`, colours[index]));
      root.style.setProperty("--c-radius", `${radius}px`);
      root.style.setProperty("--c-font", font === "Share Tech Mono" ? "\"Neon Mono\", Consolas, monospace" : `"${font}", "Segoe UI", sans-serif`);
    }
    return neon;
  }

  // -- the HUD look's parts --------------------------------------------------------------
  function head(model) {
    // Who's on watch on the left; on the right, short chips that never wrap:
    // chat connected, whether the stream is live (once Twitch has said),
    // and muted or holding.
    const connected = model.status === "connected";
    const who = node("strong", "stream-who", `${String(model.companion || "").toUpperCase()} ON WATCH`);
    const chips = node("span", "stream-chips");
    chips.appendChild(node("span", `stream-state ${connected ? "live" : model.status === "off" ? "off" : "wait"}`,
      connected ? "CHAT" : model.status === "off" ? "CHAT OFF" : "CONNECTING"));
    if (model.on_air === true) chips.appendChild(node("span", "stream-air on", "ON AIR"));
    else if (model.on_air === false) chips.appendChild(node("span", "stream-air off", "OFF AIR"));
    if (model.muted) chips.appendChild(node("em", "stream-flag muted", "MUTED"));
    if (model.holding) chips.appendChild(node("em", "stream-flag holding", "HOLDING"));
    dom["stream-head"].title = model.channel ? `#${model.channel}` : "";
    dom["stream-head"].replaceChildren(who, chips);
  }

  function banner(model) {
    const item = model.banner;
    dom["stream-banner"].hidden = !item;
    if (!item) return;
    const kinds = {raid: "RAID", sub: "THANK YOU", win: "RESULT", rank: "PROMOTION", named: "WORLD NAMED", welcome: "WELCOME", muted: "CHAT"};
    dom["stream-banner"].className = `stream-banner kind-${item.kind}`;
    dom["stream-banner"].replaceChildren(node("span", "banner-tag", kinds[item.kind] || "CHAT"), node("p", "", item.text));
  }

  function game(model) {
    const item = model.game;
    dom["stream-game"].hidden = !item;
    if (!item) return;
    const box = dom["stream-game"];
    box.className = `stream-game kind-${item.kind}${item.done ? " done" : ""}`;
    const title = node("header", "game-head");
    title.append(node("span", "game-tag", item.done ? "SETTLED" : item.open ? "GAME ON" : "WAITING ON THE GAME"), node("strong", "", item.title || "GAME"));
    const parts = [title];
    if (!item.done) parts.push(node("p", "game-prompt", item.prompt || ""));
    if (item.open && item.closes_in != null) {
      const bar = node("div", "game-timer");
      const fill = node("i");
      const key = `${item.kind}|${item.title}`;
      timerMax[key] = Math.max(timerMax[key] || 0, Number(item.closes_in) || 0);
      fill.style.setProperty("--left", `${Math.max(0, Math.min(100, (Number(item.closes_in) / Math.max(1, timerMax[key])) * 100))}%`);
      bar.append(fill, node("b", "", `${Math.max(0, Number(item.closes_in))} s`));
      parts.push(bar);
    }
    if (Array.isArray(item.choices) && item.choices.length) {
      const list = node("ol", "game-choices");
      const most = Math.max(1, ...item.choices.map((choice) => Number(choice.votes) || 0));
      for (const choice of item.choices) {
        const row = node("li", item.answer && item.answer === choice.name ? "won" : "");
        const bar = node("i");
        bar.style.setProperty("--w", `${((Number(choice.votes) || 0) / most) * 100}%`);
        row.append(node("b", "", `${choice.n}`), node("span", "", choice.name), node("small", "", `by ${choice.by}`), node("em", "", `${choice.votes}`), bar);
        list.appendChild(row);
      }
      parts.push(list);
    } else if ((item.tally || []).length) {
      const list = node("ul", "game-tally");
      const most = Math.max(1, ...item.tally.map((row) => Number(row.count) || 0));
      for (const row of item.tally) {
        const line = node("li", item.answer != null && String(row.value).toUpperCase() === String(item.answer).toUpperCase() ? "won" : "");
        const bar = node("i");
        bar.style.setProperty("--w", `${((Number(row.count) || 0) / most) * 100}%`);
        line.append(node("b", "", String(row.value).toUpperCase()), bar, node("em", "", `${row.count}`));
        list.appendChild(line);
      }
      parts.push(list);
    }
    const foot = node("footer", "game-foot");
    if (item.done && item.answer != null) foot.append(node("span", "", "ANSWER"), node("b", "", item.answer_name || String(item.answer)));
    else if (Array.isArray(item.choices) && item.stage === "vote") foot.append(node("span", "", "VOTES"), node("b", "", `${item.choices.reduce((sum, choice) => sum + (Number(choice.votes) || 0), 0)}`));
    else if (Array.isArray(item.choices)) foot.append(node("span", "", "NAMES IN"), node("b", "", `${item.choices.length} of 4`));
    else foot.append(node("span", "", "GUESSES"), node("b", "", `${item.guesses || 0}`));
    parts.push(foot);
    box.replaceChildren(...parts);
  }

  function cards(model, neon) {
    if (neon) { dom["stream-cards"].replaceChildren(); return; }
    const list = (model.cards || []).map((card, index) => {
      const item = node("article", `stream-card${index === 0 ? " newest" : ""}`);
      const who = node("header");
      const name = node("b", "", `${BADGES[card.badge] ? `${BADGES[card.badge]} ` : ""}${card.who}`);
      name.style.color = chatColour(card.color);
      who.append(name, node("span", "asked", card.asked || ""));
      item.append(who, node("p", "", card.text || ""));
      return item;
    });
    dom["stream-cards"].replaceChildren(...list);
  }

  function hint(model, neon) {
    const quiet = neon ? !(model.lines || []).length : !(model.cards || []).length;
    const show = Boolean(model.hint) && quiet && !model.game && !model.credits;
    dom["stream-hint"].hidden = !show;
    if (show) dom["stream-hint"].replaceChildren(node("span", "", "ASK THE CREW"), node("b", "", model.commands || ""));
  }

  // -- the Neon chat box ------------------------------------------------------------------
  function badge(name) {
    const role = ROLE_BADGES[name];
    if (!role) return null;
    const mark = node("span", "badge", role[0]);
    mark.style.background = role[1];
    return mark;
  }

  function line(item) {
    const row = node("div", "msg");
    row.dataset.id = item.id;
    const meta = node("span", "meta");
    const body = node("span", "body");
    if (item.kind === "chat") {
      for (const name of item.badges || []) { const mark = badge(name); if (mark) meta.appendChild(mark); }
      const name = node("span", "name", item.who);
      const colour = nameColour(item);
      name.style.color = colour;
      name.style.setProperty("--name-color", colour);
      meta.appendChild(name);
      if (item.first) { meta.appendChild(node("span", "chip", "First chat")); row.classList.add("first"); }
      else if (item.back) meta.appendChild(node("span", "chip back", "Welcome back"));
      for (const part of item.fragments || []) {
        if (part.type === "emote" && /^https:\/\/(static-cdn\.jtvnw\.net|cdn\.betterttv\.net)\//.test(String(part.url || ""))) {
          const img = node("img", "emote");
          img.src = part.url;
          img.alt = part.text || "";
          body.appendChild(img);
        } else body.append(String(part.text || ""));
      }
    } else if (item.kind === "event") {
      const [glyph, colour] = EVENT_ROWS[item.type] || ["✦", "#00F0FF"];
      row.classList.add("evt");
      row.style.setProperty("--ec", colour);
      const name = node("span", "name", `${glyph} ${item.who}`);
      name.style.color = colour;
      name.style.setProperty("--name-color", colour);
      meta.appendChild(name);
      body.append(String(item.text || ""));
    } else {
      // The companion: its answers and its own lines, in its colour.
      row.classList.add("crew");
      const name = node("span", "name", `✦ ${item.who}`);
      const colour = OFFICER_HUE[item.identity] || "#00F0FF";
      name.style.color = colour;
      name.style.setProperty("--name-color", colour);
      row.style.setProperty("--crew", colour);
      meta.appendChild(name);
      if (item.kind === "reply" && item.to) meta.appendChild(node("span", "chip to", `@${item.to} ${item.asked || ""}`.trim()));
      body.append(String(item.text || ""));
    }
    row.append(meta, node("span", "sep", " "), body);
    return row;
  }

  function lines(model, neon) {
    const list = dom["stream-lines"];
    if (!neon || model.credits) { list.hidden = true; return; }
    list.hidden = false;
    const items = model.lines || [];
    const key = JSON.stringify(items);
    if (key === listKey) return;
    listKey = key;
    // Only the lines new since last time slide in.
    const rows = items.map((item) => {
      const row = line(item);
      if (!shownLines.has(item.id) && shownLines.size) row.classList.add("arrive");
      return row;
    });
    shownLines = new Set(items.map((item) => item.id));
    list.replaceChildren(...rows);
  }

  // -- the end credits ----------------------------------------------------------------------
  // Built once a roll starts, then left to scroll.
  function credits(model) {
    const roll = model.credits;
    dom.stream.classList.toggle("rolling", Boolean(roll));
    dom["stream-credits"].hidden = !roll;
    if (!roll) { creditsKey = ""; return; }
    const key = `${roll.started}|${roll.until}`;
    if (key === creditsKey) return;
    creditsKey = key;
    const reel = node("div", "reel");
    const block = (title, rows) => {
      if (!rows.length) return;
      const section = node("section", "reel-block");
      section.appendChild(node("h3", "", title));
      for (const row of rows) section.appendChild(row);
      reel.appendChild(section);
    };
    reel.appendChild(node("h2", "", roll.title || "TONIGHT'S FLIGHT"));
    reel.appendChild(node("p", "reel-sub", `WITH ${String(roll.companion || "").toUpperCase()} ON WATCH`));
    block("THE FLIGHT", (roll.figures || []).map((row) => { const pair = node("p", "pair"); pair.append(node("span", "", row.label), node("b", "", row.value)); return pair; }));
    block("TOP CREW", (roll.top || []).map((row) => { const pair = node("p", "pair"); pair.append(node("span", "", `${row.name} · ${row.rank}`), node("b", "", `${row.points} pts`)); return pair; }));
    block("WORLDS NAMED BY CHAT", (roll.named || []).map((row) => { const named = node("p", "named"); named.append(node("b", "", `“${row.name}”`), node("span", "", `${row.world} · by ${row.by}`)); return named; }));
    block("RAIDS", (roll.raids || []).map((row) => node("p", "", `${row.name} · ${row.viewers} aboard`)));
    block("SUPPORTED BY", (roll.supporters || []).map((name) => node("p", "", name)));
    if (Number(roll.bits)) block("BITS", [node("p", "", `${roll.bits} in all`)]);
    block("THE CREW", (roll.crew || []).map((name) => node("p", "crew", name)));
    reel.appendChild(node("p", "reel-signoff", `“${roll.signoff || ""}”`));
    reel.appendChild(node("p", "reel-made", "VOID COMPASS"));
    // The reel scrolls once through the window in the time it has.
    const seconds = Math.max(20, Math.min(240, Math.round((Number(roll.until) - Date.now() / 1000) || 60)));
    reel.style.setProperty("--roll", `${seconds}s`);
    dom["stream-credits"].replaceChildren(reel);
  }

  function render(snapshot = {}) {
    VoidCompassOverlay.applyTheme(dom.stream, snapshot.theme || {}, snapshot.effects || {});
    VoidCompassOverlay.fitToWindow(dom.stream, DESIGN_WIDTH, snapshot.effects || {});
    const model = snapshot.stream || null;
    dom.stream.classList.toggle("empty", !model);
    if (!model) return;
    for (const officer of OFFICERS) dom.stream.classList.toggle(`by-${officer}`, model.identity === officer);
    const neon = applyLook(model);
    head(model);
    banner(model);
    game(model);
    cards(model, neon);
    lines(model, neon);
    hint(model, neon);
    credits(model);
  }

  function contentHeight() {
    if (dom.stream.classList.contains("rolling")) return 620;
    // The chat box keeps its size; the HUD look grows with what it shows.
    if (dom.stream.classList.contains("neon")) return Number.parseInt(getComputedStyle(dom.stream).getPropertyValue("--box-h"), 10) || 480;
    return VoidCompassOverlay.designHeight(dom.stream, MIN_HEIGHT);
  }

  VoidCompassOverlay.startPolling({token, overlay, render, contentHeight, interval: 250});
})();
