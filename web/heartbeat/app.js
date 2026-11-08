(() => {
  "use strict";
  const params = new URLSearchParams(location.search);
  const root = document.getElementById("heartbeat");
  const canvas = document.getElementById("orb");
  const motionPreference = window.matchMedia("(prefers-reduced-motion: reduce)");
  const orb = new window.HeartbeatOrb(canvas);
  window.heartbeatOrb = orb;
  let poller = null;
  let asterModel = {};
  let asterReduced = false;
  // The live poll repaints with the same palette as the snapshot did: without
  // it a Theme accent flipped between two colours every second.
  let shownPalette;
  let companionIdentity = "watcher";
  // 5.7.7: whose display is showing; a crewmate off watch takes it while they speak.
  let shownIdentity = null;
  const thoughtBox = document.getElementById("thought");
  const thoughtFrame = thoughtBox.querySelector(".thought-box");
  const thoughtHead = thoughtBox.querySelector(".thought-head");
  const thoughtText = thoughtBox.querySelector(".thought-words");
  const thoughtAnswers = thoughtBox.querySelector(".thought-answers");
  let thoughtId = null;
  // Its voice (5.5.4): what it's saying now, from /api/live.
  let speech = null;
  // Listening to you (5.7.1): push to talk, from /api/live.
  const hearingRing = document.getElementById("hearing");
  let hearing = null;
  let hearingStage = "";
  function showHearing(state) {
    const stage = state ? String(state.stage || "") : "";
    hearingRing.hidden = !stage;
    if (stage !== hearingStage) {
      hearingRing.dataset.stage = stage;
      // Working out what you said: it narrows its eye to listen.
      if (stage === "hearing") orb.think?.(900);
      hearingStage = stage;
    }
    hearingRing.style.setProperty("--hear", stage === "listening" ? String(Math.min(1, (Number(state.level) || 0) * 6)) : "0");
  }

  const {typingPlan, finalWords, paintParts, createPresenter} = window.CompanionCaption;
  window.heartbeatTyping = {typingPlan, finalWords};
  const caption = createPresenter({
    paint: parts => paintParts(thoughtText, parts),
    onDone: done => thoughtBox.classList.toggle("done", done),
    onThink: pause => orb.think?.(pause),
    onStart: (duration, voiced) => { if (!voiced) orb.speak?.(duration); },
  });

  // The line above a thought (5.5.3.5): what kind it is, from the mind (a
  // memory and where it sits in the story, an echo and what stirred it), or
  // for an everyday remark simply the Watcher.
  function headingFor(thought) {
    return thought.heading ? String(thought.heading) : "THE WATCHER";
  }

  // A thought: a moment's thought first (the aperture tightens), then it
  // types out as the eye speaks it, the eye showing how it feels about it.
  function showThought(thought, reduced, eye, nature, who = companionIdentity) {
    const style = (thought && thought.style) || {};
    document.body.classList.toggle("still", Boolean(reduced));
    document.body.classList.toggle("thought-backdrop", style.backdrop !== false);
    const companion = who !== "watcher";
    const colours = window.CompanionColours?.resolve(who, eye, getComputedStyle(document.documentElement).getPropertyValue("--accent").trim());
    if (colours) document.body.style.setProperty("--companion-eye-colour", colours.primary);
    document.body.dataset.thoughtColour = style.colour === "accent" ? "accent" : style.colour === "eye" ? (companion ? "companion" : eye === "hal" ? "red" : ["cyan", "brass"].includes(eye) ? eye : "accent") : "bright";
    document.body.dataset.thoughtSize = ["small", "large"].includes(style.size) ? style.size : "standard";
    if (!thought || !thought.text) {
      thoughtId = null;
      caption.clear();
      thoughtBox.hidden = true;
      document.body.classList.remove("thought-left");
      document.documentElement.style.removeProperty("--orb-top");
      return;
    }
    document.body.classList.toggle("thought-left", thought.side === "left");
    // Near a screen edge the window grows away from it, so the orb isn't
    // always in the middle: the bridge says where its top is.
    document.documentElement.style.setProperty("--orb-top", `${Math.max(0, Number(thought.orb_top) || 0)}px`);
    thoughtHead.hidden = style.heading === false;
    const changed = caption.show(thought, {scope: companionIdentity, nature, reduced});
    thoughtId = thought.id;
    thoughtBox.hidden = false;
    if (!changed) return;
    thoughtFrame.dataset.kind = String(thought.kind || "");
    thoughtHead.textContent = headingFor(thought);
    const answers = thought.question?.answers || [];
    thoughtAnswers.hidden = !answers.length;
    thoughtAnswers.textContent = answers.map((answer, index) => `${index + 1} · ${answer.label}`).join("   ");
    if (thought.effect && !reduced) orb.play?.({effect: thought.effect, tone: "accent", weight: 1}, performance.now());
    orb.showMood?.(thought.mood);
    if (thought.voice && !liveAsking) { clearTimeout(livePoll); listen(); }
  }

  function render(snapshot = {}) {
    const effects = snapshot.effects || {};
    const palette = VoidCompassOverlay.applyTheme(root, snapshot.theme || {}, effects);
    shownPalette = palette;
    const model = snapshot.heartbeat || {};
    const stalled = Boolean(model.stalled);
    const identity = model.orb?.identity || "watcher";
    if (identity !== companionIdentity) { companionIdentity = identity; caption.clear(); thoughtId = null; }
    asterReduced = motionPreference.matches || Boolean(effects.reduced_motion);
    // 5.7.7: a crewmate off watch, speaking (an order, a remark): their own
    // display takes the overlay while they talk, then it's back to whoever
    // has the watch. Live voice levels still come for the one on watch.
    const speaker = String(model.thought?.speaker || "");
    const guest = speaker && speaker !== identity ? speaker : "";
    const guestEye = guest ? model.thought.speaker_accent || (guest === "watcher" ? model.orb?.eye : "signature") : "";
    const shown = guest ? {...model, orb: {...(model.orb || {}), identity: guest, accent: guestEye, ...(guest === "watcher" ? {eye: guestEye} : {})},
      moment: {...(model.moment || {}), service: Number(model.thought.speaker_service) || 0}} : model;
    const showing = guest || identity;
    // Only a guest stepping in or out fades; switching who's on watch doesn't.
    const guestBefore = root.classList.contains("guest");
    if (shownIdentity !== null && showing !== shownIdentity && (guest || guestBefore) && !asterReduced) {
      root.classList.remove("guest-swap");
      void root.offsetWidth;
      root.classList.add("guest-swap");
    }
    shownIdentity = showing;
    root.classList.toggle("guest", Boolean(guest));
    asterModel = shown;
    orb.setSuspended?.(showing !== "watcher");
    window.AsterCompanion?.update(canvas, shown, {speech, hearing}, {palette, reducedMotion: asterReduced});
    window.CrewCompanion?.update(canvas, shown, {speech, hearing}, {palette, reducedMotion: asterReduced});

    // You pressed talk: the ring shows now, not on the next slow poll.
    if (model.hearing && model.hearing !== hearingStage && !liveAsking) {
      window.clearTimeout(livePoll);
      listen();
    }
    // The orb at its own size while a thought shows, when a long one makes
    // the window taller than the orb; otherwise it simply fills the window.
    const orbSize = Number((model.orb || {}).size) || 0;
    if (orbSize > 0) document.documentElement.style.setProperty("--orb-size", `${orbSize}px`);
    else document.documentElement.style.removeProperty("--orb-size");
    root.classList.toggle("stalled", stalled);
    orb.update({
      palette,
      eye: (shown.orb || {}).eye,
      crt: effects.crt !== false,
      reducedMotion: motionPreference.matches || Boolean(effects.reduced_motion),
      stalled,
      events: model.events,
      statusSeq: model.status_seq,
      // Overlay Studio's Liveliness and Idle motions, and Status.json's
      // danger, heat, fuel and scooping for the Watcher's mood.
      liveliness: (model.orb || {}).liveliness,
      idle: (model.orb || {}).idle !== false,
      // Its own Frame rate (5.5.7); the page's frame cap already follows it.
      frameRate: (model.orb || {}).frame_rate,
      focusMovement: (model.orb || {}).focus_movement,
      vitals: model.vitals,
      // What the commander is doing (the HUD's state), for how it watches.
      state: model.state,
      // Where the other overlays are, its nature, and its memory of you.
      overlays: model.overlays,
      personality: model.personality,
      memory: model.memory,
      // What its story has done to the eye (5.6.1).
      story: (model.orb || {}).story,
      // Your standing with it, as service pips on its housing (5.7.7).
      service: (shown.moment || {}).service,
    });
    if (model.orb?.renderer_logging) orb.watchRenderer((renderer, reason) => {
      const token = encodeURIComponent(params.get("token") || "");
      const overlay = encodeURIComponent(params.get("overlay") || "heartbeat");
      fetch(`/api/watcher-renderer?token=${token}&overlay=${overlay}`, {
        method: "POST", body: JSON.stringify({renderer, ...(reason ? {reason} : {})}),
      }).then((response) => response.arrayBuffer()).catch(() => {});
    });
    showThought(model.thought, asterReduced, showing !== "watcher" ? shown.orb.accent : shown.orb?.eye, model.personality, showing);
    const companionLabel = {aster:"Aster",axiom:"Axiom",meridian:"Meridian",lyra:"Lyra"}[showing] || "Journal watcher";
    const label = stalled ? `${companionLabel}: feed quiet`
      : orb.lastEvent ? `${companionLabel}: ${orb.lastEvent}` : companionLabel;
    root.setAttribute("aria-label", label);
    root.title = label;
  }

  // The Music player's live levels (5.5.3.2): the eye moves with the music.
  // Asked often while something plays, once a second otherwise.
  let livePoll = 0;
  let liveAsking = false;
  async function listen() {
    let playing = false;
    liveAsking = true;
    const requestedIdentity = companionIdentity, requestedScope = asterModel.thought?.scope;
    try {
      const response = await fetch(`/api/live?token=${encodeURIComponent(params.get("token") || "")}&overlay=${encodeURIComponent(params.get("overlay") || "heartbeat")}`,
        {cache: "no-store"});
      let received = {};
      if (response.ok) received = await response.json();
      else await response.arrayBuffer();
      const accepted = requestedIdentity === companionIdentity && (!received.identity || received.identity === companionIdentity)
        && (!requestedScope || !asterModel.thought?.scope || requestedScope === asterModel.thought.scope);
      const live = accepted ? received : {};
      playing = Boolean(live.playing) && Array.isArray(live.bands) && live.bands.length > 0;
      orb.music?.(playing ? live.bands : null);
      speech = live.speech && typeof live.speech === "object" ? live.speech : null;
      caption.live(speech);
      orb.voice?.(speech ? Number(speech.level) || 0 : null);
      hearing = live.hearing && typeof live.hearing === "object" ? live.hearing : null;
      window.AsterCompanion?.update(canvas, asterModel, live, {palette: shownPalette, reducedMotion: asterReduced});
      window.CrewCompanion?.update(canvas, asterModel, live, {palette: shownPalette, reducedMotion: asterReduced});
      showHearing(hearing);
    } catch (_error) {
      orb.music?.(null);
      speech = null;
      caption.live(null);
      orb.voice?.(null);
      hearing = null;
      showHearing(null);
    }
    liveAsking = false;
    // Quick while music plays, it speaks or listens, or a spoken thought waits for its voice.
    const busy = playing || speech || hearing || (thoughtId !== null && !thoughtBox.classList.contains("done"));
    livePoll = window.setTimeout(listen, busy && !document.hidden ? 100 : 1000);
  }
  listen();

  window.addEventListener("aster-three-ready", () => poller?.rerender());
  window.addEventListener("crew-three-ready", () => poller?.rerender());
  window.addEventListener("companion-colours-ready", () => poller?.rerender());
  document.addEventListener("visibilitychange", () => caption.setVisible(!document.hidden));
  motionPreference.addEventListener("change", () => poller?.rerender());
  window.addEventListener("pagehide", () => { window.clearTimeout(livePoll); caption.destroy(); orb.dispose(); });
  poller = VoidCompassOverlay.startPolling({
    token: params.get("token") || "", overlay: params.get("overlay") || "heartbeat",
    render, contentHeight: () => orb.size || 54, interval: 160,
  });
})();
