// Hatchling's first-class Cockpit home (5.6.7). The journal remains the
// source of truth; this page runs the shared 3D model and life simulation.

const NEEDS = [
  ["hunger", "Nourishment", "◌"], ["mood", "Morale", "✦"], ["clean", "Habitat", "⌁"],
  ["health", "Health", "＋"], ["energy", "Energy", "◒"],
];
const SPECIES_ORDER = ["larva", "bot", "sample"];
const SAMPLE_KINDS = ["bacterium", "tubus", "fungoida"];
const SPECIES_NAMES = {larva: "Thargoid larva", bot: "Remlok bot", sample: "Exobiology sample"};
const PLACE_NAMES = {space: "In flight", supercruise: "Supercruise", docked: "Docked", landed: "On the surface", srv: "Riding in the SRV", away: "On foot"};
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[char]));
const clamp = (value, low = 0, high = 100) => Math.max(low, Math.min(high, Number(value) || 0));

let root = null;
let ui = null;
let live = {};
let life = null;
let rendererPromise = null;
let active = false;
let frame = 0;
let lastFrame = 0;
let lastMusic = 0;
let lastCanvasSize = "";
let mini = null;
let draft = {species: "larva", kind: "bacterium", name: ""};
let lastMiniMarkup = "";

function getPet() { return live?.pet || null; }
function startLife() {
  if (!life && window.HatchlingLife?.create) {
    life = window.HatchlingLife.create({size: 220, range: 90, top: 170, speech: true});
  }
}

function loadRenderer() {
  if (window.Hatchling3D) return Promise.resolve(true);
  if (!rendererPromise) {
    rendererPromise = import("/assets/hatchling-3d.js").then(() => true).catch((error) => {
      rendererPromise = null;
      ui?.showToast?.(`Three.js habitat unavailable: ${error.message}`);
      return false;
    });
  }
  return rendererPromise;
}

function build(rootNode, workshop) {
  root = rootNode;
  ui = workshop;
  root.classList.remove("loading-panel");
  root.innerHTML = `<div class="hatchling-deck">
    <div class="hl-masthead"><div><small>SHIPBOARD COMPANION // PERSONAL HABITAT</small><p>A little life aboard, shaped by the places you go and the way you fly.</p></div>
      <div class="hl-link-state"><i></i><span>JOURNAL LINK</span><b data-hl-link>LIVE</b><em>30 FPS</em></div></div>
    <div class="hl-main-grid">
      <section class="hl-scene-panel" aria-label="Hatchling habitat">
        <div class="hl-scene-top"><div><small>HABITAT // <b data-hl-place>AWAITING JOURNAL</b></small><strong data-hl-scene-name>Ready for a new shipmate</strong></div><span data-hl-stage>EGG BAY</span></div>
        <div class="hl-scene">
          <div class="hl-scene-nebula" aria-hidden="true"></div><div class="hl-scene-stars" aria-hidden="true"></div>
          <div class="hl-scene-beam" aria-hidden="true"></div><canvas data-hl-canvas aria-label="Animated three dimensional Hatchling. Click it for a pat." role="img"></canvas>
          <div class="hl-ground-grid" aria-hidden="true"></div>
          <div class="hl-scene-caption"><span data-hl-cue>WAITING FOR A LITTLE ADVENTURE</span><b data-hl-frame>THREE.JS // 30 FPS</b></div>
          <div class="hl-mini-game" data-hl-mini hidden></div>
        </div>
        <div class="hl-scene-foot"><span><i data-hl-mood-dot></i><b data-hl-mood>NO COMPANION ABOARD</b></span><span data-hl-trip></span></div>
      </section>
      <aside class="hl-care-panel">
        <section class="hl-card hl-vitals"><header><div><small>CONDITION</small><h4>Habitat readout</h4></div><span data-hl-status>STANDBY</span></header><div class="hl-needs" data-hl-needs></div>
          <div class="hl-notice" data-hl-notice hidden></div>
          <div class="hl-care-actions" data-hl-actions></div>
          <div class="hl-feed-list" data-hl-feed hidden></div>
        </section>
        <section class="hl-card hl-identity"><header><div><small>COMPANION RECORD</small><h4 data-hl-identity-title>Choose an egg</h4></div><span data-hl-age>—</span></header><div data-hl-identity></div></section>
      </aside>
    </div>
    <div class="hl-lower-grid">
      <section class="hl-card hl-activities"><header><div><small>PLAY TOGETHER</small><h4>Short games</h4></div><span>THEIR FAVOURITE: <b data-hl-favourite>—</b></span></header>
        <div class="hl-game-cards" data-hl-games></div>
      </section>
      <section class="hl-card hl-character"><header><div><small>FIELD NOTES</small><h4>Little discoveries</h4></div><span data-hl-personality>PERSONALITY GROWS WITH YOU</span></header><div class="hl-collections" data-hl-collections></div></section>
      <section class="hl-card hl-log"><header><div><small>SHIP'S JOURNAL</small><h4>Recent moments</h4></div><span>JOURNAL DRIVEN</span></header><ol data-hl-log></ol></section>
    </div>
    <div class="hl-welcome" data-hl-welcome hidden></div>
  </div>`;
  root.addEventListener("click", onClick);
  root.addEventListener("change", onChange);
  root.addEventListener("input", onInput);
  const canvas = root.querySelector("[data-hl-canvas]");
  canvas?.addEventListener("pointermove", onPointerMove);
  canvas?.addEventListener("click", onCanvasClick);
  startLife();
}

function action(act, value = {}) {
  return ui?.command("workspace", {page: "hatchling", operation: "action", act, value});
}

function stateFlags(pet) {
  const egg = !pet || pet.stage === "egg";
  const dormant = Boolean(pet?.dormant);
  const asleep = Boolean(pet?.asleep);
  return {egg, dormant, asleep, awake: Boolean(pet) && !egg && !dormant && !asleep};
}

function fillNeeds(pet) {
  const host = root.querySelector("[data-hl-needs]");
  if (!pet) {
    host.innerHTML = `<p class="hl-empty-hint">Hatch an egg to start its live care record.</p>`;
    return;
  }
  host.innerHTML = NEEDS.map(([key, label, icon]) => {
    const value = clamp(pet.needs?.[key]);
    const low = value < 26;
    return `<div class="hl-need${low ? " low" : ""}"><span class="hl-need-icon">${icon}</span><div><div class="hl-need-label"><b>${label}</b><span>${Math.round(value)}%</span></div><div class="hl-meter"><i style="width:${value}%"></i></div></div></div>`;
  }).join("");
}

function fillActions(pet) {
  const host = root.querySelector("[data-hl-actions]");
  const feed = root.querySelector("[data-hl-feed]");
  if (!pet) {
    host.innerHTML = `<div class="hl-empty-hint">Your companion will live here in real time, even when the deck is closed.</div>`;
    feed.hidden = true;
    return;
  }
  const flags = stateFlags(pet);
  const disabled = flags.egg || flags.dormant || flags.asleep;
  if (flags.dormant) {
    host.innerHTML = `<button class="hl-action hl-revive" data-hl-act="revive" ${pet.medicine?.length ? "" : "disabled"}><b>REVIVE</b><span>${pet.medicine?.length ? `Use ${esc(pet.medicine.join(" / "))}` : `Needs ${esc(pet.medicine?.join(" / ") || "medicine from a market")}`}</span></button>`;
  } else {
    host.innerHTML = `<div class="hl-action-grid">
      <button class="hl-action hl-primary" data-hl-open-feed ${disabled ? "disabled" : ""}><b>Feed</b><span>From the larder</span></button>
      <button class="hl-action" data-hl-act="vent" ${disabled ? "disabled" : ""}><b>Vent hold</b><span>Freshen habitat</span></button>
      <button class="hl-action" data-hl-act="medicine" ${disabled || (!pet.sick && pet.needs?.health >= 90) ? "disabled" : ""}><b>Medicine</b><span>${pet.sick ? "Feeling unwell" : "Keep it healthy"}</span></button>
      <button class="hl-action" data-hl-act="lights" ${flags.egg || flags.dormant ? "disabled" : ""}><b>${flags.asleep ? "Wake up" : "Lights out"}</b><span>${flags.asleep ? "Bring it back" : "Let it rest"}</span></button>
      <button class="hl-action" data-hl-act="pet" ${flags.egg || flags.dormant || flags.asleep ? "disabled" : ""}><b>Give a pat</b><span>A little reassurance</span></button>
    </div>`;
  }
  const larder = pet.larder || [];
  feed.innerHTML = larder.length ? `<small>SHIP'S LARDER</small>${larder.map((item) => `<button data-hl-feed-item="${esc(item.id)}"><span><b>${esc(item.name)}</b><em>${esc(item.kind)}</em></span><strong>×${Math.max(0, Number(item.count) || 0)}</strong></button>`).join("")}`
    : `<small>SHIP'S LARDER</small><p>Empty. Supplies return with time or from a market.</p>`;
  feed.hidden = true;
}

function duration(ageHours) {
  const hours = Math.max(0, Number(ageHours) || 0);
  if (hours >= 24) return `${Math.floor(hours / 24)}d ${Math.floor(hours % 24)}h aboard`;
  return `${Math.floor(hours)}h aboard`;
}

function fillIdentity(pet, data) {
  const host = root.querySelector("[data-hl-identity]");
  if (!pet) {
    const species = data.species || {};
    const options = SPECIES_ORDER.map((id) => `<button class="hl-species${draft.species === id ? " selected" : ""}" data-hl-species="${id}"><b>${esc(species[id]?.name || SPECIES_NAMES[id])}</b><span>${esc(species[id]?.blurb || "A new shipmate for the journey.")}</span></button>`).join("");
    const kinds = draft.species === "sample" ? `<label class="hl-form-row"><span>Sample family</span><select data-hl-kind>${SAMPLE_KINDS.map((id) => `<option value="${id}" ${draft.kind === id ? "selected" : ""}>${esc(data.kinds?.[id] || id)}</option>`).join("")}</select></label>` : "";
    host.innerHTML = `<div class="hl-species-list">${options}</div>${kinds}<label class="hl-form-row"><span>Call sign</span><input data-hl-name maxlength="16" autocomplete="off" placeholder="Choose a name" value="${esc(draft.name)}"></label><button class="hl-hatch-button" data-hl-act="hatch">HATCH THIS EGG <span>THE JOURNEY STARTS HERE</span></button>
      ${data.collection?.length ? `<p class="hl-collection-count">${data.collection.length} grown form${data.collection.length === 1 ? "" : "s"} recorded</p>` : ""}`;
    root.querySelector("[data-hl-identity-title]").textContent = "Choose an egg";
    root.querySelector("[data-hl-age]").textContent = "NEW LIFE";
    return;
  }
  const earned = (pet.outfits || []).filter((item) => item.earned);
  const options = [{id: "", label: "No outfit"}, ...earned.map((item) => ({id: item.id, label: item.label}))];
  host.innerHTML = `<div class="hl-record-species"><b>${esc(pet.species_name)}${pet.kind_name ? ` · ${esc(pet.kind_name)}` : ""}</b><span>${esc(pet.form_name || pet.stage)}${pet.trip?.name ? ` · on ${esc(pet.trip.name)}` : ""}</span></div>
    <label class="hl-form-row"><span>Call sign</span><div class="hl-rename"><input data-hl-name maxlength="16" value="${esc(pet.name)}" aria-label="Hatchling name"><button data-hl-act="rename">SAVE</button></div></label>
    <label class="hl-form-row"><span>Earned outfit</span><select data-hl-outfit>${options.map((item) => `<option value="${esc(item.id)}" ${pet.outfit === item.id ? "selected" : ""}>${esc(item.label)}</option>`).join("")}</select></label>
    <div class="hl-earned-line"><span>TOYS FOUND</span><b>${(pet.toys || []).length}</b><span>TRICKS LEARNED</span><b>${(pet.tricks || []).length}</b></div>`;
  root.querySelector("[data-hl-identity-title]").textContent = pet.name || "Companion";
  root.querySelector("[data-hl-age]").textContent = duration(pet.age_hours);
}

function fillCollections(pet) {
  const host = root.querySelector("[data-hl-collections]");
  if (!pet) {
    host.innerHTML = `<p class="hl-empty-hint">First discoveries, favorite toys and new tricks will collect here.</p>`;
    root.querySelector("[data-hl-personality]").textContent = "PERSONALITY GROWS WITH YOU";
    root.querySelector("[data-hl-favourite]").textContent = "—";
    return;
  }
  root.querySelector("[data-hl-personality]").textContent = pet.trait ? `${pet.trait.toUpperCase()} TEMPERAMENT` : "STILL FINDING ITS FEET";
  root.querySelector("[data-hl-favourite]").textContent = pet.favourite_game || "—";
  const toys = (pet.toys || []).map((item) => `<span class="hl-chip hl-toy">${esc(item.label)}</span>`).join("");
  const tricks = (pet.tricks || []).map((item) => `<span class="hl-chip hl-trick">${esc(item)}</span>`).join("");
  const dreams = (pet.dreams || []).map((item) => `<span class="hl-chip">${esc(item)}</span>`).join("");
  const badges = (pet.badges || []).map((item) => `<span class="hl-chip hl-badge">${esc(item.text || item.name)}</span>`).join("");
  host.innerHTML = `<div class="hl-collection-group"><small>TOYS FROM YOUR JOURNEYS</small><div>${toys || `<em>It hasn't brought a toy home yet.</em>`}</div></div>
    <div class="hl-collection-group"><small>TRICKS</small><div>${tricks || `<em>Learned by spending time together.</em>`}</div></div>
    ${dreams ? `<div class="hl-collection-group"><small>RECENT DREAMS</small><div>${dreams}</div></div>` : ""}
    ${badges ? `<div class="hl-collection-group"><small>EXPEDITION BADGES</small><div>${badges}</div></div>` : ""}
    <div class="hl-favourites"><span>FAVOURITE FOOD <b>${esc(pet.favourite_food || "—")}</b></span><span>LAST PLACE <b>${esc(pet.world?.name || PLACE_NAMES[pet.place] || "Space")}</b></span></div>`;
}

function fillJournal(pet) {
  const host = root.querySelector("[data-hl-log]");
  if (!pet?.log?.length) {
    host.innerHTML = `<li class="hl-empty-hint">Its first journal moment will appear here.</li>`;
    return;
  }
  host.innerHTML = pet.log.slice(0, 6).map((item) => `<li><i class="${item.tone === "good" ? "good" : item.tone === "bad" ? "bad" : ""}"></i><span>${esc(item.text)}</span><small>${new Date((Number(item.at) || 0) * 1000).toLocaleDateString(undefined, {day: "numeric", month: "short"})}</small></li>`).join("");
}

function fillWelcome(pet) {
  const host = root.querySelector("[data-hl-welcome]");
  if (!pet?.welcome) { host.hidden = true; host.innerHTML = ""; return; }
  host.hidden = false;
  host.innerHTML = `<div><b>WELCOME BACK, ${esc(pet.name.toUpperCase())}</b><p>${(pet.welcome.lines || []).map(esc).join(" ")}</p></div><button data-hl-act="welcomed">GLAD TO BE BACK</button>`;
}

function fillScene(pet) {
  const stage = root.querySelector("[data-hl-stage]");
  const cue = root.querySelector("[data-hl-cue]");
  const place = root.querySelector("[data-hl-place]");
  const mood = root.querySelector("[data-hl-mood]");
  const status = root.querySelector("[data-hl-status]");
  root.querySelector("[data-hl-scene-name]").textContent = pet ? pet.name : "Ready for a new shipmate";
  place.textContent = pet ? (PLACE_NAMES[pet.place] || "In flight").toUpperCase() : "AWAITING JOURNAL";
  stage.textContent = pet ? pet.dormant ? "HIBERNATING" : pet.asleep ? "RESTING" : (pet.stage || "hatchling").toUpperCase() : "EGG BAY";
  mood.textContent = pet ? `${pet.mood_word || "Settling in"}${pet.wants ? ` · ${pet.wants}` : ""}`.toUpperCase() : "NO COMPANION ABOARD";
  status.textContent = !pet ? "STANDBY" : pet.dormant ? "HIBERNATING" : pet.sick ? "NEEDS CARE" : pet.asleep ? "RESTING" : "DOING WELL";
  root.querySelector("[data-hl-mood-dot]").classList.toggle("low", Boolean(pet && (pet.dormant || pet.sick || pet.needs?.mood < 25)));
  root.querySelector("[data-hl-trip]").textContent = pet?.trip ? `EXPEDITION // ${pet.trip.to || pet.trip.name}` : pet?.ship ? `ABOARD // ${pet.ship}` : "";
  const words = pet?.chat?.text || pet?.log?.[0]?.text || "A quiet moment between jumps.";
  cue.textContent = words.toUpperCase();
  root.querySelector("[data-hl-link]").textContent = pet ? "CONNECTED" : "READY TO HATCH";
}

function fillGames(pet) {
  const host = root.querySelector("[data-hl-games]");
  const {awake} = stateFlags(pet);
  host.innerHTML = `<button class="hl-game-card" data-hl-game="limpet" ${awake ? "" : "disabled"}><span class="hl-game-glyph">⌁</span><b>Catch the limpet</b><small>Three catches before it darts off</small><em>SHORT GAME // 12 SECONDS</em></button>
    <button class="hl-game-card" data-hl-game="thargon" ${awake ? "" : "disabled"}><span class="hl-game-glyph">✣</span><b>Where did the Thargon go?</b><small>Track it through the Guardian stones</small><em>MEMORY GAME // 10 SECONDS</em></button>`;
}

function update(data) {
  live = data || {};
  const pet = getPet();
  fillScene(pet);
  fillNeeds(pet);
  fillActions(pet);
  fillIdentity(pet, live);
  fillCollections(pet);
  fillJournal(pet);
  fillWelcome(pet);
  fillGames(pet);
  const notice = root.querySelector("[data-hl-notice]");
  const freshNotice = live.notice?.text && Number(live.notice.at) > Date.now() / 1000 - 20;
  notice.hidden = !freshNotice;
  notice.textContent = freshNotice ? live.notice.text : "";
  startLife();
  if (mini) drawMini();
}

function requestFrame() {
  if (active && !frame) frame = requestAnimationFrame(drawFrame);
}

function setHatchlingActive(value) {
  active = Boolean(value);
  if (!active && frame) {
    cancelAnimationFrame(frame);
    frame = 0;
    lastFrame = 0;
  } else if (active) {
    loadRenderer().then(() => requestFrame());
    requestFrame();
  }
}

function paintBackground(ctx, width, height, time) {
  const gradient = ctx.createLinearGradient(0, 0, 0, height);
  gradient.addColorStop(0, "rgba(3, 10, 19, .12)");
  gradient.addColorStop(.76, "rgba(4, 14, 20, .12)");
  gradient.addColorStop(1, "rgba(1, 7, 11, .82)");
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, width, height);
  for (let i = 0; i < 42; i += 1) {
    const x = ((i * 173.3) % width + width) % width;
    const y = ((i * 83.7) % (height * .7) + height * .04) % height;
    const pulse = .22 + (Math.sin(time * .5 + i * 3.1) + 1) * .2;
    ctx.globalAlpha = pulse;
    ctx.fillStyle = i % 7 === 0 ? "#9bffe0" : "#d9ecff";
    ctx.fillRect(x, y, i % 7 === 0 ? 2 : 1, i % 7 === 0 ? 2 : 1);
  }
  ctx.globalAlpha = 1;
}

function drawFrame(timestamp) {
  frame = 0;
  if (!active || !root?.isConnected) return;
  if (document.hidden) return;
  requestFrame();
  startLife();
  if (timestamp - lastFrame < 33) return;
  const delta = lastFrame ? Math.min(.08, (timestamp - lastFrame) / 1000) : 1 / 30;
  lastFrame = timestamp;
  const canvas = root.querySelector("[data-hl-canvas]");
  const box = canvas?.getBoundingClientRect();
  if (!canvas || !box?.width || !box?.height) return;
  const dpr = Math.min(1.5, window.devicePixelRatio || 1);
  const sizeKey = `${Math.round(box.width * dpr)}:${Math.round(box.height * dpr)}`;
  if (sizeKey !== lastCanvasSize) {
    lastCanvasSize = sizeKey;
    canvas.width = Math.round(box.width * dpr);
    canvas.height = Math.round(box.height * dpr);
  }
  const ctx = canvas.getContext("2d", {alpha: true});
  if (!ctx) return;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const width = box.width, height = box.height, seconds = timestamp / 1000;
  paintBackground(ctx, width, height, seconds);
  const pet = getPet();
  const size = Math.min(250, height * .63, width * .55);
  const originY = height * .72 - size * .44;
  const centerX = width * .5;
  if (pet && life) {
    life.resize({size, range: Math.min(100, width * .24), top: height * .35, ink: 12, speech: true});
    life.step(delta, pet, {busy: Boolean(mini)});
    if (timestamp - lastMusic > 120) {
      const heard = window.voidcompassMusicLevels?.();
      life.hear(heard?.bands, Boolean(heard?.playing));
      lastMusic = timestamp;
    }
    life.back(ctx, pet, centerX, originY);
    life.drawPet(ctx, pet, {x: centerX, y: originY, size, t: seconds, aura: false});
    life.front(ctx, pet, centerX, originY);
  } else {
    const preview = {species: draft.species, kind: draft.species === "sample" ? draft.kind : "", stage: "egg", hatch_minutes: 18,
      needs: {mood: 76}, asleep: false, dormant: false};
    window.Hatchling3D?.draw(ctx, preview, {x: centerX, y: originY, size: size * .82, t: seconds, aura: false});
  }
  if (mini) drawMiniPosition(width, height, timestamp);
}

function onPointerMove(event) {
  if (!life || !getPet() || !root) return;
  const rect = event.currentTarget.getBoundingClientRect();
  life.lookAt([clamp((event.clientX - rect.left - rect.width / 2) / (rect.width * .28), -1, 1),
    clamp((event.clientY - rect.top - rect.height * .48) / (rect.height * .3), -1, 1)], .6);
}

function onCanvasClick(event) {
  const pet = getPet();
  if (!pet || !life || pet.stage === "egg" || pet.dormant || pet.asleep || mini) return;
  life.kick(.8);
  if (event.detail) action("pet");
}

function openMini(game) {
  const pet = getPet();
  if (!stateFlags(pet).awake) return;
  const now = performance.now();
  mini = game === "limpet"
    ? {game, started: now, deadline: now + 12000, caught: 0, sent: false}
    : {game, started: now, deadline: now + 10000, phase: "watch", correct: Math.floor(Math.random() * 3), sent: false};
  lastMiniMarkup = "";
  drawMini();
}

function finishMini(won) {
  if (!mini || mini.sent) return;
  mini.sent = true;
  mini.won = Boolean(won);
  mini.finishedAt = performance.now();
  const game = mini.game;
  if (life && getPet()) life.play(game === "limpet" ? "keepy" : "tag", getPet());
  action("play", {game, won: Boolean(won)});
  ui?.showToast?.(won ? "A fine game. The Hatchling loved that." : "A close one. The Hatchling had fun anyway.");
  drawMini(true);
}

function drawMini(force = false) {
  const host = root?.querySelector("[data-hl-mini]");
  if (!host || !mini) { if (host) { host.hidden = true; host.innerHTML = ""; } return; }
  host.hidden = false;
  const title = mini.game === "limpet" ? "CATCH THE LIMPET" : "WHERE DID THE THARGON GO?";
  let body = "";
  if (mini.sent) {
    body = `<div class="hl-mini-result"><b>${mini.won ? "CAUGHT IT!" : "NICE TRY"}</b><span>${mini.won ? "The Thargon is showing off." : "It wants another round sometime."}</span><button data-hl-mini-close>BACK TO HABITAT</button></div>`;
  } else if (mini.game === "limpet") {
    body = `<div class="hl-mini-score"><b data-hl-catches>${mini.caught} / 3 CATCHES</b><span data-hl-countdown>12 S</span></div><div class="hl-limpet-zone"><button class="hl-limpet-target" data-hl-catch aria-label="Catch the limpet">✣</button></div><small>CLICK THE MOVING LIMPET THREE TIMES</small>`;
  } else {
    const watching = mini.phase === "watch";
    body = `<div class="hl-mini-score"><b>${watching ? "WATCH THE THARGON" : "WHICH STONE?"}</b><span data-hl-countdown>8 S</span></div><div class="hl-shells">${[0, 1, 2].map((index) => `<button class="hl-shell" data-hl-shell="${index}" ${watching ? "disabled" : ""}><i>${watching && mini.correct === index ? "✣" : "?"}</i><b>STONE 0${index + 1}</b></button>`).join("")}</div><small>${watching ? "KEEP ITS LAST POSITION IN MIND" : "SELECT THE STONE HIDING THE THARGON"}</small>`;
  }
  const markup = `<div class="hl-mini-card"><header><div><small>HABITAT GAME</small><b>${title}</b></div><button data-hl-mini-close aria-label="Close game">×</button></header>${body}</div>`;
  if (force || markup !== lastMiniMarkup) {
    host.innerHTML = markup;
    lastMiniMarkup = markup;
  }
}

function drawMiniPosition(width, height, timestamp) {
  if (!mini || mini.sent) return;
  const elapsed = timestamp - mini.started;
  const countdown = root.querySelector("[data-hl-countdown]");
  if (mini.game === "limpet") {
    const left = Math.max(0, mini.deadline - timestamp);
    if (countdown) countdown.textContent = `${Math.ceil(left / 1000)} S`;
    const zone = root.querySelector(".hl-limpet-zone");
    const target = root.querySelector("[data-hl-catch]");
    if (zone && target) {
      const phase = elapsed / 1000;
      target.style.left = `${50 + Math.sin(phase * 2.7) * 35}%`;
      target.style.top = `${50 + Math.cos(phase * 3.1) * 28}%`;
    }
    if (left <= 0) finishMini(false);
  } else {
    const watchLength = 1400;
    if (elapsed >= watchLength && mini.phase === "watch") {
      mini.phase = "pick";
      lastMiniMarkup = "";
      drawMini(true);
    }
    const left = Math.max(0, mini.deadline - timestamp);
    if (countdown) countdown.textContent = `${Math.ceil(left / 1000)} S`;
    if (left <= 0) finishMini(false);
  }
}

function onClick(event) {
  const species = event.target.closest("[data-hl-species]");
  if (species) {
    draft.species = species.dataset.hlSpecies;
    update(live);
    return;
  }
  const act = event.target.closest("[data-hl-act]");
  if (act && !act.disabled) {
    const verb = act.dataset.hlAct;
    if (verb === "hatch") {
      const data = live.species?.[draft.species];
      const names = data?.names || ["Pip"];
      action("hatch", {species: draft.species, kind: draft.species === "sample" ? draft.kind : "", name: draft.name.trim() || names[0]});
    } else if (verb === "rename") {
      const name = root.querySelector("[data-hl-name]")?.value || "";
      action("rename", {name});
    } else if (verb === "welcomed") action("welcomed");
    else action(verb);
    return;
  }
  if (event.target.closest("[data-hl-open-feed]")) {
    const feed = root.querySelector("[data-hl-feed]");
    feed.hidden = !feed.hidden;
    return;
  }
  const food = event.target.closest("[data-hl-feed-item]");
  if (food) { action("feed", {item: food.dataset.hlFeedItem}); root.querySelector("[data-hl-feed]").hidden = true; return; }
  const game = event.target.closest("[data-hl-game]");
  if (game && !game.disabled) { openMini(game.dataset.hlGame); return; }
  const catcher = event.target.closest("[data-hl-catch]");
  if (catcher && mini?.game === "limpet" && !mini.sent) {
    mini.caught += 1;
    const label = root.querySelector("[data-hl-catches]");
    if (label) label.textContent = `${mini.caught} / 3 CATCHES`;
    if (mini.caught >= 3) finishMini(true);
    return;
  }
  const shell = event.target.closest("[data-hl-shell]");
  if (shell && mini?.game === "thargon" && mini.phase === "pick" && !mini.sent) {
    finishMini(Number(shell.dataset.hlShell) === mini.correct);
    return;
  }
  if (event.target.closest("[data-hl-mini-close]")) { mini = null; lastMiniMarkup = ""; drawMini(); }
}

function onInput(event) {
  if (event.target.matches("[data-hl-name]") && !getPet()) draft.name = event.target.value.slice(0, 16);
}

function onChange(event) {
  if (event.target.matches("[data-hl-kind]")) draft.kind = event.target.value;
  else if (event.target.matches("[data-hl-outfit]")) action("wear", {outfit: event.target.value});
}

function renderHatchling(data, workshop) {
  const host = document.getElementById("hatchling-workspace");
  if (!host) return;
  if (!root || root !== host || !root.querySelector(".hatchling-deck")) build(host, workshop);
  else ui = workshop;
  update(data);
  requestFrame();
}

document.addEventListener("visibilitychange", () => {
  if (!document.hidden) requestFrame();
});

export {renderHatchling, setHatchlingActive};
