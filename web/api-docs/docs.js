// Void Compass Local API docs (5.5.7): one section at a time, find, tabs,
// copy, TRY on every endpoint and the live status pill. The page is complete
// without this script; it only arranges and adds.
(() => {
  "use strict";
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const esc = (text) => String(text ?? "").replace(/[&<>"]/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"})[c]);
  const store = {
    get(key) { try { return localStorage.getItem(key); } catch { return null; } },
    set(key, value) { try { localStorage.setItem(key, value); } catch { /* private window */ } },
  };
  const ORIGIN = location.protocol.startsWith("http") ? location.origin : "http://127.0.0.1:7380";
  const API = `${ORIGIN}/api/v1`;
  const main = $("#main");
  const sections = $$("section.doc");
  const titleOf = (section) => section.dataset.section === "overview" ? "Overview" : ($("h2", section)?.textContent || "");
  document.documentElement.classList.add("js");

  // The examples say 127.0.0.1:7380; show the address this page is really on.
  if (ORIGIN !== "http://127.0.0.1:7380") {
    for (const code of $$("code")) {
      if (code.textContent.includes("http://127.0.0.1:7380")) code.textContent = code.textContent.split("http://127.0.0.1:7380").join(ORIGIN);
    }
  }
  $(".base").textContent = API;

  // -- highlighting ------------------------------------------------------------
  const JS_WORDS = /\b(?:const|let|var|function|return|if|else|for|of|in|new|await|async|true|false|null|undefined|document|console)\b/y;
  const RULES = {
    json: [[/"(?:[^"\\\n]|\\.)*"(?=\s*:)/y, "key"], [/"(?:[^"\\\n]|\\.)*"/y, "str"], [/-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?/y, "num"], [/\b(?:true|false|null)\b/y, "kw"]],
    http: [[/^(?:GET|POST)\b/my, "verb"], [/https?:\/\/[^\s"]+/y, "url"], [/"(?:[^"\\\n]|\\.)*"(?=\s*:)/y, "key"], [/"(?:[^"\\\n]|\\.)*"/y, "str"], [/-?\d+(?:\.\d+)?/y, "num"], [/\b(?:true|false|null)\b/y, "kw"]],
    python: [[/#.*/y, "com"], [/[fr]?(?:"""[\s\S]*?"""|'(?:[^'\\\n]|\\.)*'|"(?:[^"\\\n]|\\.)*")/y, "str"],
      [/\b(?:import|from|as|def|return|if|elif|else|for|in|while|try|except|continue|break|and|or|not|is|None|True|False|lambda|with)\b/y, "kw"],
      [/\b(?:print|sorted|len|str|int|requests)\b/y, "fn"], [/\b\d+(?:\.\d+)?\b/y, "num"]],
    javascript: [[/\/\/.*/y, "com"], [/`(?:[^`\\]|\\.)*`|'(?:[^'\\\n]|\\.)*'|"(?:[^"\\\n]|\\.)*"/y, "str"], [JS_WORDS, "kw"], [/\b\d+(?:\.\d+)?\b/y, "num"]],
    powershell: [[/#.*/y, "com"], [/"(?:[^"`\n]|`.)*"|'[^'\n]*'/y, "str"], [/\$[\w:]+/y, "var"],
      [/\b(?:while|if|else|foreach|try|catch|true|false)\b/iy, "kw"], [/\b[A-Z][a-z]+-[A-Z]\w+\b/y, "fn"], [/-[A-Z]\w+/y, "flag"]],
    bat: [[/"(?:[^"\\\n]|\\.)*"/y, "str"], [/\bcurl\b/y, "fn"], [/-[A-Za-z]\b/y, "flag"], [/\^$/my, "com"], [/https?:\/\/\S+/y, "url"]],
    html: [[/<!--[\s\S]*?-->/y, "com"], [/<\/?[a-zA-Z][\w-]*|\/?>/y, "tag"], [/\b[a-z-]+(?==")/y, "attr"],
      [/`(?:[^`\\]|\\.)*`|'(?:[^'\\\n]|\\.)*'|"(?:[^"\\\n]|\\.)*"/y, "str"], [/\/\/.*/y, "com"], [JS_WORDS, "kw"], [/\b\d+(?:\.\d+)?(?:px|s|%)?\b/y, "num"]],
  };
  function highlight(text, lang) {
    const rules = RULES[lang];
    if (!rules) return esc(text);
    let out = "";
    let plain = "";
    let at = 0;
    scan: while (at < text.length) {
      for (const [pattern, kind] of rules) {
        pattern.lastIndex = at;
        const match = pattern.exec(text);
        if (match && match[0]) {
          out += esc(plain) + `<span class="t-${kind}">${esc(match[0])}</span>`;
          plain = "";
          at += match[0].length;
          continue scan;
        }
      }
      plain += text[at];
      at += 1;
    }
    return out + esc(plain);
  }

  // -- copying -----------------------------------------------------------------
  async function copy(text, button) {
    let done = false;
    try {
      await navigator.clipboard.writeText(text);
      done = true;
    } catch {
      const area = Object.assign(document.createElement("textarea"), {value: text});
      area.style.cssText = "position:fixed;opacity:0;top:0";
      document.body.append(area);
      area.select();
      try { done = document.execCommand("copy"); } catch { done = false; }
      area.remove();
    }
    if (!button) return;
    const was = button.dataset.label || button.textContent;
    button.dataset.label = was;
    button.textContent = done ? "COPIED" : "CTRL+C";
    button.classList.toggle("done", done);
    clearTimeout(button._reset);
    button._reset = setTimeout(() => { button.textContent = was; button.classList.remove("done"); }, 1400);
  }
  const LANG_NAMES = {http: "HTTP", json: "JSON", python: "Python", powershell: "PowerShell", bat: "Command Prompt", javascript: "JavaScript", html: "HTML", text: "Text"};
  function dressCode(pre) {
    const code = $("code", pre);
    const lang = pre.dataset.lang || "text";
    code.innerHTML = highlight(code.textContent, lang);
    const frame = document.createElement("div");
    frame.className = "code";
    frame.innerHTML = `<div class="code-bar"><span>${esc(LANG_NAMES[lang] || lang)}</span><button type="button" class="mini">COPY</button></div>`;
    pre.replaceWith(frame);
    frame.append(pre);
    $("button", frame).addEventListener("click", (event) => copy(code.textContent, event.currentTarget));
  }
  $$("main pre").forEach(dressCode);
  $(".base").addEventListener("click", (event) => copy(API, null).then(() => {
    event.target.textContent = "COPIED";
    setTimeout(() => { event.target.textContent = API; }, 1000);
  }));

  // -- tabs ----------------------------------------------------------------------
  for (const group of $$(".tabs")) {
    const tabs = $$(":scope > .tab", group);
    const bar = document.createElement("div");
    bar.className = "tab-bar";
    bar.setAttribute("role", "tablist");
    const pick = (label, remember) => {
      const chosen = tabs.find((tab) => tab.dataset.label === label) || tabs[0];
      for (const tab of tabs) tab.hidden = tab !== chosen;
      for (const button of $$("button", bar)) button.setAttribute("aria-selected", String(button.dataset.label === chosen.dataset.label));
      if (remember) {
        store.set("vc-docs-tab", chosen.dataset.label);
        // The same choice wherever it's offered (Python here, Python there).
        for (const other of $$(".tabs")) if (other !== group) other._pick?.(chosen.dataset.label, false, true);
      }
    };
    group._pick = (label, remember, onlyIfThere) => {
      if (onlyIfThere && !tabs.some((tab) => tab.dataset.label === label)) return;
      pick(label, remember);
    };
    for (const tab of tabs) {
      const button = document.createElement("button");
      button.type = "button";
      button.setAttribute("role", "tab");
      button.dataset.label = tab.dataset.label;
      button.textContent = tab.dataset.label;
      button.addEventListener("click", () => pick(tab.dataset.label, true));
      bar.append(button);
    }
    group.prepend(bar);
    const saved = store.get("vc-docs-tab");
    pick(tabs.some((tab) => tab.dataset.label === saved) ? saved : tabs[0].dataset.label, false);
  }

  // -- endpoints: copy and TRY -------------------------------------------------
  const DEFAULTS = {page: "explore", id: "survey", overlay: "survey", name: "", address: ""};
  let control = true;
  function exampleQuery(card) {
    // A GET line in the same section ("GET /api/v1/events?types=...") gives the query to start from.
    const {method, path} = card.dataset;
    if (path.includes("{")) return "";
    const section = card.closest("section.doc");
    for (const code of $$('pre[data-lang="http"] code', section)) {
      const line = code.textContent.split("\n")[0].trim();
      if (line.startsWith(`${method} ${path}?`)) return line.slice(method.length + 1 + path.length);
    }
    return "";
  }
  function exampleBody(card) {
    for (const code of $$("p code", card)) {
      const text = code.textContent.trim();
      if (!text.startsWith("{")) continue;
      try { return JSON.stringify(JSON.parse(text), null, 2); } catch { /* not JSON */ }
    }
    return "";
  }
  function dressEndpoint(card) {
    const {method, path} = card.dataset;
    const acts = document.createElement("span");
    acts.className = "acts";
    const copyButton = Object.assign(document.createElement("button"), {type: "button", className: "mini", textContent: "COPY URL"});
    copyButton.addEventListener("click", () => copy(ORIGIN + path, copyButton));
    acts.append(copyButton);
    if (!path.endsWith("/docs")) {
      const tryButton = Object.assign(document.createElement("button"), {type: "button", className: "mini try-it", textContent: method === "POST" ? "SEND" : "TRY"});
      tryButton.setAttribute("aria-expanded", "false");
      tryButton.addEventListener("click", () => toggleTry(card, tryButton));
      acts.append(tryButton);
    }
    $("header", card).append(acts);
  }
  function toggleTry(card, button) {
    const open = $(".try", card);
    if (open) {
      open._stop?.();
      open.remove();
      button.setAttribute("aria-expanded", "false");
      return;
    }
    button.setAttribute("aria-expanded", "true");
    const {method, path} = card.dataset;
    const stream = path.endsWith("/events/stream");
    const panel = document.createElement("div");
    panel.className = "try";
    const pieces = path.split(/(\{[a-z_|-]+\})/).map((part) => {
      const param = part.match(/^\{([a-z_|-]+)\}$/);
      if (!param) return `<b>${esc(part)}</b>`;
      const value = DEFAULTS[param[1]] || "";
      return `<input data-param="${esc(param[1])}" value="${esc(value)}" size="${Math.max(4, value.length)}" placeholder="${esc(param[1])}" aria-label="${esc(param[1])}">`;
    }).join("");
    const query = exampleQuery(card);
    const body = method === "POST" ? exampleBody(card) : "";
    panel.innerHTML = `
      <div class="try-row">
        <span class="try-url">${esc(ORIGIN)}${pieces}${method === "GET" ? `<input class="q" value="${esc(query)}" placeholder="?query" aria-label="Query">` : ""}</span>
        <button type="button" class="send">${stream ? "LISTEN" : "SEND"}</button>
      </div>
      ${method === "POST" ? `<textarea spellcheck="false" placeholder="JSON body (optional)" aria-label="Body">${esc(body)}</textarea>
      <p class="note warn">${control ? "This really does it: Void Compass changes as you send." : "Allow control is off in Settings, so this answers 403."}</p>` : ""}
      ${stream ? `<p class="note">Events appear here as they happen. Jump, dock, or let the Watcher think.</p>` : ""}
      <div class="out" hidden></div>`;
    card.append(panel);
    for (const input of $$("[data-param]", panel)) input.addEventListener("input", () => { input.size = Math.max(4, input.value.length); });
    const send = $(".send", panel);
    const go = () => (stream ? listen(panel, send) : run(panel, method));
    send.addEventListener("click", go);
    panel.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && (event.target.tagName === "INPUT" || event.ctrlKey)) { event.preventDefault(); go(); }
    });
    if (method === "GET" && !stream) go();
  }
  function urlOf(panel) {
    let url = ORIGIN;
    for (const node of $(".try-url", panel).childNodes) {
      if (node.nodeName === "B") url += node.textContent;
      else if (node.dataset?.param) url += encodeURIComponent(node.value.trim());
    }
    const query = $(".q", panel)?.value.trim() || "";
    return url + (query && !query.startsWith("?") ? `?${query}` : query);
  }
  const size = (n) => n < 1024 ? `${n} B` : `${(n / 1024).toFixed(n < 10240 ? 1 : 0)} KB`;
  async function run(panel, method) {
    const out = $(".out", panel);
    out.hidden = false;
    out.innerHTML = `<div class="out-meta">SENDING…</div>`;
    const options = {method, headers: {}};
    if (method === "POST") {
      const body = $("textarea", panel).value.trim();
      if (body) {
        try { JSON.parse(body); } catch {
          out.innerHTML = `<div class="out-meta"><span class="st bad">NOT SENT</span> The body isn't valid JSON.</div>`;
          return;
        }
        options.body = body;
        options.headers["Content-Type"] = "application/json";
      }
    }
    const started = performance.now();
    let response;
    let text;
    try {
      response = await fetch(urlOf(panel), options);
      text = await response.text();
    } catch {
      out.innerHTML = `<div class="out-meta"><span class="st bad">NO ANSWER</span> Is Void Compass running, with the Local API on?</div>`;
      return;
    }
    const ms = Math.round(performance.now() - started);
    let shown = text;
    try { shown = JSON.stringify(JSON.parse(text), null, 2); } catch { /* not JSON */ }
    const LIMIT = 60000;
    const cut = shown.length > LIMIT;
    out.innerHTML = `<div class="out-meta"><span class="st${response.ok ? "" : " bad"}">${response.status} ${esc(response.statusText || "")}</span><span>${ms} ms</span><span>${size(text.length)}</span><button type="button" class="mini">COPY</button></div>
      <pre data-lang="json"><code>${highlight(cut ? shown.slice(0, LIMIT) : shown, "json")}</code></pre>
      ${cut ? `<button type="button" class="more">SHOW ALL ${size(shown.length)}</button>` : ""}`;
    $(".out-meta button", out).addEventListener("click", (event) => copy(shown, event.currentTarget));
    $(".more", out)?.addEventListener("click", (event) => {
      $("code", out).innerHTML = highlight(shown, "json");
      event.currentTarget.remove();
    });
  }
  function summary(type, data) {
    if (!data || typeof data !== "object") return String(data ?? "");
    if (type === "journal") return [data.event, data.StarSystem || data.BodyName || data.StationName || data.Name_Localised || ""].filter(Boolean).join(" · ");
    if (type === "thought" || type === "voice") return data.text || "";
    if (type === "music") return `${data.playing ? "▶" : "❚❚"} ${data.title || ""}${data.artist ? ` · ${data.artist}` : ""}`;
    if (type === "feed") return `${data.tag || ""} ${data.message || ""}`;
    return JSON.stringify(data).slice(0, 160);
  }
  function listen(panel, button) {
    if (panel._source) { panel._stop(); return; }
    const out = $(".out", panel);
    out.hidden = false;
    out.innerHTML = `<div class="out-meta"><span class="st">LISTENING</span><span class="n">0 events</span></div><div class="feed"><span class="wait">Waiting for something to happen…</span></div>`;
    const feed = $(".feed", out);
    let count = 0;
    const source = new EventSource(urlOf(panel));
    panel._source = source;
    panel._stop = () => {
      source.close();
      panel._source = null;
      button.textContent = "LISTEN";
      $(".st", out).textContent = "STOPPED";
    };
    button.textContent = "STOP";
    source.onerror = () => { $(".st", out).textContent = "RECONNECTING"; };
    source.onopen = () => { $(".st", out).textContent = "LISTENING"; };
    source.onmessage = null;
    const types = ["journal", "status", "cargo", "navroute", "market", "shiplocker", "feed", "thought", "overlay", "voice", "music"];
    for (const type of types) {
      source.addEventListener(type, (message) => {
        let item = {};
        try { item = JSON.parse(message.data); } catch { /* keep going */ }
        $(".wait", feed)?.remove();
        const row = document.createElement("div");
        row.innerHTML = `<time>${new Date().toLocaleTimeString([], {hour12: false})}</time><span class="ty">${esc(type)}</span><span class="tx" title="${esc(JSON.stringify(item.data))}">${esc(summary(type, item.data))}</span>`;
        feed.prepend(row);
        while (feed.children.length > 60) feed.lastElementChild.remove();
        count += 1;
        $(".n", out).textContent = `${count} event${count === 1 ? "" : "s"}`;
      });
    }
  }
  $$(".endpoint").forEach(dressEndpoint);

  // -- sections, one at a time -------------------------------------------------
  const navLinks = $$(".rail nav a[href^='#']");
  for (const section of sections) {
    const h2 = $("h2", section);
    if (h2 && section.dataset.group) h2.dataset.kicker = section.dataset.group;
    const endpoints = $$(".endpoint", section).length;
    const link = navLinks.find((a) => a.getAttribute("href") === `#${section.dataset.section}`);
    if (link && endpoints) link.insertAdjacentHTML("beforeend", `<span class="count">${endpoints}</span>`);
  }
  // The overview leads to every section.
  const overview = sections.find((section) => section.dataset.section === "overview");
  if (overview) {
    const cards = sections.filter((section) => section !== overview).map((section, index) => {
      const first = $(":scope > p", section)?.textContent || "";
      const sentence = (first.match(/^.*?[.!?](\s|$)/) || [first])[0].trim();
      const endpoints = $$(".endpoint", section).length;
      const topics = $$("h3", section).length;
      const extra = endpoints ? `${endpoints} endpoint${endpoints === 1 ? "" : "s"}` : topics ? `${topics} topic${topics === 1 ? "" : "s"}` : "";
      return `<a class="card${index < 3 ? " lead" : ""}" href="#${esc(section.dataset.section)}"><small>${esc(section.dataset.group)}</small><b>${esc(titleOf(section))}</b><span>${esc(sentence)}</span>${extra ? `<em>${extra}</em>` : ""}</a>`;
    });
    overview.insertAdjacentHTML("beforeend", `<div class="cards">${cards.join("")}</div>`);
  }
  sections.forEach((section, index) => {
    const before = sections[index - 1];
    const after = sections[index + 1];
    section.insertAdjacentHTML("beforeend", `<footer class="pager">${before ? `<a class="prev" href="#${esc(before.dataset.section)}"><small>‹ PREVIOUS</small>${esc(titleOf(before))}</a>` : ""}${after ? `<a class="next" href="#${esc(after.dataset.section)}"><small>NEXT ›</small>${esc(titleOf(after))}</a>` : ""}</footer>`);
  });

  const rail = $("#rail");
  const railFoot = document.createElement("div");
  railFoot.className = "rail-foot";
  railFoot.innerHTML = `<label><input type="checkbox" id="all-on-one"> All on one page</label>`;
  rail.append(railFoot);
  const allBox = $("#all-on-one", railFoot);
  let current = null;

  function subNav(section) {
    const links = [];
    for (const node of $$("h3, .endpoint", section)) {
      if (node.tagName === "H3") links.push(`<a href="#${esc(node.id)}">${esc(node.textContent)}</a>`);
      else links.push(`<a href="#${esc(node.id)}"><span class="verb verb-${node.dataset.method.toLowerCase()}">${esc(node.dataset.method)}</span><code>${esc(node.dataset.path.replace(/^\/api\/v1/, "") || "/")}</code></a>`);
    }
    return links.length ? `<div class="sub">${links.join("")}</div>` : "";
  }
  function show(hash, scroll = true) {
    const id = decodeURIComponent(String(hash || "").replace(/^#/, ""));
    const target = id ? document.getElementById(id) : null;
    const section = target?.closest("section.doc") || sections[0];
    if (!section) return;
    const paged = !allBox.checked;
    main.classList.toggle("paged", paged);
    main.classList.toggle("all", !paged);
    for (const each of sections) each.classList.toggle("shown", each === section);
    if (section !== current) {
      $$(".rail .sub").forEach((sub) => sub.remove());
      const link = navLinks.find((a) => a.getAttribute("href") === `#${section.dataset.section}`);
      link?.insertAdjacentHTML("afterend", subNav(section));
      current = section;
    }
    for (const a of navLinks) a.classList.toggle("on", a.getAttribute("href") === `#${section.dataset.section}`);
    for (const a of $$(".rail .sub a")) a.classList.toggle("on", a.getAttribute("href") === `#${id}`);
    document.title = `${titleOf(section)} · Void Compass API`;
    rail.classList.remove("open");
    $(".rail-toggle").setAttribute("aria-expanded", "false");
    if (!scroll) return;
    const heading = target && (target === section || target.matches("h1, h2"));
    if (target && !heading) {
      target.scrollIntoView({block: "start"});
      if (target.classList.contains("endpoint")) {
        target.classList.remove("flash");
        void target.offsetWidth;
        target.classList.add("flash");
      }
    } else if (paged) {
      window.scrollTo(0, 0);
    } else {
      (target || section).scrollIntoView({block: "start"});
    }
  }
  allBox.checked = store.get("vc-docs-all") === "1";
  allBox.addEventListener("change", () => {
    store.set("vc-docs-all", allBox.checked ? "1" : "0");
    show(location.hash);
  });
  window.addEventListener("hashchange", () => show(location.hash));
  // Links to the place already open still move there.
  document.addEventListener("click", (event) => {
    const link = event.target.closest?.("a[href^='#']");
    if (link && link.getAttribute("href") === location.hash) show(location.hash);
  });
  $(".rail-toggle").addEventListener("click", (event) => {
    const open = rail.classList.toggle("open");
    event.currentTarget.setAttribute("aria-expanded", String(open));
  });

  // -- find --------------------------------------------------------------------
  const find = $("#find");
  const results = $("#results");
  const railNav = $(".rail nav");
  const index = [];
  // Words of each block apart, and none of the buttons' labels.
  const TEXT_BLOCKS = "p, li, th, td, h3, h4, h5, figcaption, blockquote, pre";
  const textOf = (node) => (node.matches(TEXT_BLOCKS) ? [node] : $$(TEXT_BLOCKS, node)).map((n) => n.textContent).join(" ");
  for (const section of sections) {
    const title = titleOf(section);
    index.push({kind: "section", href: `#${section.dataset.section}`, title, where: section.dataset.group || "Void Compass API", text: textOf(section)});
    for (const h3 of $$("h3", section)) {
      let text = "";
      for (let node = h3.nextElementSibling; node && node.tagName !== "H3"; node = node.nextElementSibling) text += ` ${textOf(node)}`;
      index.push({kind: "topic", href: `#${h3.id}`, title: h3.textContent, where: title, text});
    }
    for (const card of $$(".endpoint", section)) {
      index.push({kind: "endpoint", href: `#${card.id}`, title: `${card.dataset.method} ${card.dataset.path}`, where: title, text: $("p", card)?.textContent || "", method: card.dataset.method, path: card.dataset.path});
    }
  }
  const literal = (text) => text.replace(/[.*+?^$()|[\]{}\\]/g, "\\$&");
  const mark = (text, terms) => {
    let html = esc(text);
    for (const term of terms) html = html.replace(new RegExp(`(${literal(esc(term))})`, "ig"), "<mark>$1</mark>");
    return html;
  };
  function snippet(text, term) {
    const flat = text.replace(/\s+/g, " ");
    const at = flat.toLowerCase().indexOf(term);
    if (at < 0) return "";
    const start = Math.max(0, at - 40);
    return `${start ? "…" : ""}${flat.slice(start, at + term.length + 70)}…`;
  }
  let picked = 0;
  function search() {
    const terms = find.value.trim().toLowerCase().split(/\s+/).filter(Boolean);
    if (!terms.length) {
      results.hidden = true;
      railNav.hidden = false;
      return;
    }
    const hit = (entry, field) => terms.every((term) => field(entry).toLowerCase().includes(term));
    const scored = [];
    for (const entry of index) {
      const inTitle = hit(entry, (e) => `${e.title}`);
      const inText = hit(entry, (e) => `${e.title} ${e.text}`);
      if (!inTitle && !inText) continue;
      const rank = (inTitle ? 0 : 3) + {endpoint: 0, topic: 1, section: 2}[entry.kind];
      scored.push([rank, entry]);
    }
    scored.sort((a, b) => a[0] - b[0]);
    const top = scored.slice(0, 24).map(([, entry]) => entry);
    picked = 0;
    railNav.hidden = true;
    results.hidden = false;
    results.innerHTML = top.length ? top.map((entry, i) => {
      const label = entry.kind === "endpoint"
        ? `<span class="verb verb-${entry.method.toLowerCase()}">${esc(entry.method)}</span> <code>${mark(entry.path, terms)}</code>`
        : mark(entry.title, terms);
      const snip = entry.kind === "endpoint" ? entry.text : snippet(entry.text, terms[0]);
      return `<a href="${esc(entry.href)}" class="${i === 0 ? "on" : ""}"><small>${esc(entry.where)}</small>${label}${snip ? `<span class="snip">${mark(snip, terms)}</span>` : ""}</a>`;
    }).join("") : `<div class="none">Nothing matches “${esc(find.value.trim())}”.</div>`;
  }
  function choose(link) {
    if (!link) return;
    const href = link.getAttribute("href");
    find.value = "";
    search();
    find.blur();
    if (href === location.hash) show(href);
    else location.hash = href;
  }
  find.addEventListener("input", search);
  find.addEventListener("keydown", (event) => {
    const links = $$("a", results);
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (!links.length) return;
      picked = (picked + (event.key === "ArrowDown" ? 1 : links.length - 1)) % links.length;
      links.forEach((link, i) => link.classList.toggle("on", i === picked));
      links[picked].scrollIntoView({block: "nearest"});
    } else if (event.key === "Enter") {
      event.preventDefault();
      choose(links[picked]);
    } else if (event.key === "Escape") {
      find.value = "";
      search();
      find.blur();
    }
  });
  results.addEventListener("click", (event) => {
    const link = event.target.closest("a");
    if (!link) return;
    event.preventDefault();
    choose(link);
  });
  document.addEventListener("keydown", (event) => {
    const typing = event.target.closest?.("input, textarea, select, [contenteditable]");
    if (typing || event.ctrlKey || event.metaKey || event.altKey) return;
    if (event.key === "/") {
      event.preventDefault();
      if (innerWidth <= 900) rail.classList.add("open");
      find.focus();
      find.select();
    } else if (event.key === "[" || event.key === "]") {
      const at = sections.indexOf(current);
      const next = sections[at + (event.key === "]" ? 1 : -1)];
      if (next) location.hash = `#${next.dataset.section}`;
    }
  });

  // -- the live status pill and the deck's theme -------------------------------------
  const live = $("#live");
  async function checkLive() {
    try {
      const response = await fetch(`${API}/status`, {cache: "no-store"});
      if (!response.ok) throw new Error(String(response.status));
      const status = await response.json();
      const game = status.journal?.live;
      live.className = `live ${game ? "ok" : "idle"}`;
      $("span", live).textContent = `${status.commander ? `CMDR ${String(status.commander).toUpperCase()}` : "NO COMMANDER YET"} · ${game ? "GAME LIVE" : "GAME IDLE"}`;
      live.title = `Void Compass ${status.version || ""} is answering${game ? ", and the game is writing its journal" : ""}`;
    } catch {
      live.className = "live off";
      $("span", live).textContent = "NOT ANSWERING";
      live.title = "Void Compass isn't answering: is it running, with the Local API on?";
    }
  }
  fetch(API).then((r) => r.json()).then((index) => { control = index.control !== false; }).catch(() => {});
  fetch(`${API}/themes`).then((r) => r.json()).then((themes) => {
    for (const [key, value] of Object.entries(themes.colors || {})) {
      if (/^#[0-9a-f]{6}$/i.test(String(value))) document.documentElement.style.setProperty(`--${key.replace(/_/g, "-")}`, value);
    }
  }).catch(() => {});
  checkLive();
  setInterval(() => { if (!document.hidden) checkLive(); }, 10000);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) checkLive(); });

  show(location.hash, Boolean(location.hash));
})();
