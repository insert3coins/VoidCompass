(() => {
  "use strict";
  /*
   * Galnet ticker. The stories scroll right to left as one seamless loop:
   * the track holds enough copies of the sequence to cover the window, and a
   * Web Animation moves it by exactly one sequence before repeating. A change
   * of speed only changes the animation's playback rate, so the text never
   * jumps; a change of stories rebuilds the loop. Under reduced motion the
   * ticker holds one story still and steps to the next every few seconds.
   */
  const params = new URLSearchParams(location.search);
  const root = document.getElementById("ticker");
  const windowNode = document.getElementById("ticker-window");
  const track = document.getElementById("ticker-track");
  const idle = document.getElementById("ticker-idle");
  const newTag = document.getElementById("ticker-new");
  const motionPreference = window.matchMedia("(prefers-reduced-motion: reduce)");
  // The animation runs at this speed (px/s); playbackRate scales it.
  const BASE_SPEED = 75;
  const STILL_STEP_MS = 8000;
  const IDLE_TEXT = {
    off: "GALNET RELAY OFF · SWITCH IT ON IN SETTINGS",
    waiting: "AWAITING DISPATCHES",
    receiving: "RECEIVING DISPATCHES…",
    error: "GALNET UNAVAILABLE · CACHED NEWS WILL RETURN",
  };
  let animation = null;
  let contentKey = "";
  let stories = [];
  let options = {};
  let scale = 1;
  let reduced = false;
  let stillIndex = 0;
  let stillTimer = 0;
  let poller = null;

  function storyNode(story) {
    const node = document.createElement("span");
    node.className = `ticker-story${story.new ? " new" : ""}`;
    const title = document.createElement("b");
    title.textContent = story.title;
    node.append(title);
    if (options.show_date && story.stamp) {
      const date = document.createElement("time");
      date.textContent = String(story.stamp).toUpperCase();
      node.append(date);
    }
    if (story.text) {
      const body = document.createElement("span");
      body.textContent = story.text;
      node.append(body);
    }
    return node;
  }

  function sequence(list) {
    const node = document.createElement("div");
    node.className = "ticker-sequence";
    for (const story of list) {
      node.append(storyNode(story));
      const separator = document.createElement("i");
      separator.className = "ticker-sep";
      separator.textContent = "◆";
      separator.setAttribute("aria-hidden", "true");
      node.append(separator);
    }
    return node;
  }

  function speedRate() {
    return (Number(options.px_per_second) || BASE_SPEED) * scale / BASE_SPEED;
  }

  function stopStill() {
    window.clearInterval(stillTimer);
    stillTimer = 0;
  }

  function showStill() {
    stopStill();
    if (!stories.length) return;
    stillIndex %= stories.length;
    track.replaceChildren(sequence([stories[stillIndex]]));
    if (stories.length > 1) {
      stillTimer = window.setInterval(() => {
        stillIndex = (stillIndex + 1) % stories.length;
        track.replaceChildren(sequence([stories[stillIndex]]));
      }, STILL_STEP_MS);
    }
  }

  function buildLoop() {
    animation?.cancel();
    animation = null;
    stopStill();
    if (!stories.length) {
      track.replaceChildren();
      return;
    }
    if (reduced) {
      showStill();
      return;
    }
    const first = sequence(stories);
    track.replaceChildren(first);
    const width = first.getBoundingClientRect().width;
    const view = windowNode.getBoundingClientRect().width;
    if (!width || !view) return;
    // Enough copies that the window is always full while one scrolls out.
    const copies = Math.max(2, Math.ceil(view / width) + 1);
    for (let index = 1; index < copies; index += 1) track.append(first.cloneNode(true));
    animation = track.animate(
      [{transform: "translateX(0)"}, {transform: `translateX(${-width}px)`}],
      {duration: (width / BASE_SPEED) * 1000, iterations: Infinity, easing: "linear"},
    );
    animation.playbackRate = speedRate();
  }

  function render(snapshot = {}) {
    const effects = snapshot.effects || {};
    VoidCompassOverlay.applyTheme(root, snapshot.theme || {}, effects);
    const model = snapshot.ticker || {};
    const status = ["live", "waiting", "receiving", "off", "error"].includes(model.status) ? model.status : "waiting";
    const nextReduced = motionPreference.matches || Boolean(effects.reduced_motion);
    scale = Math.max(.75, Math.min(2, Number(effects.text_scale) || 1));
    options = model.options || {};
    stories = Array.isArray(model.stories) ? model.stories.filter((story) => story && story.title) : [];
    root.classList.remove("live", "waiting", "receiving", "off", "error");
    root.classList.add(status, ...(model.busy && status === "live" ? ["receiving"] : []));
    root.classList.toggle("still", nextReduced);
    const showing = status === "live" && stories.length > 0;
    track.hidden = !showing;
    idle.hidden = showing;
    idle.textContent = IDLE_TEXT[status] || IDLE_TEXT.waiting;
    newTag.hidden = !stories.some((story) => story.new);
    const label = showing ? `Galnet: ${stories[0].title}` : `Galnet: ${idle.textContent}`;
    root.setAttribute("aria-label", label);
    const key = JSON.stringify([stories, options.show_date, options.content, scale, nextReduced]);
    if (key !== contentKey) {
      contentKey = key;
      reduced = nextReduced;
      stillIndex = 0;
      buildLoop();
    } else if (animation) {
      // Speed alone changed: carry on from where the text is.
      animation.playbackRate = speedRate();
    }
  }

  // A longer or shorter bar needs a different number of copies.
  if (window.ResizeObserver) {
    let lastWidth = 0;
    new ResizeObserver(() => {
      const width = Math.round(windowNode.getBoundingClientRect().width);
      if (width && width !== lastWidth) {
        lastWidth = width;
        buildLoop();
      }
    }).observe(windowNode);
  }
  motionPreference.addEventListener("change", () => poller?.rerender());
  window.addEventListener("pagehide", () => { animation?.cancel(); stopStill(); });
  window.galnetTicker = {
    state: () => ({
      stories: stories.length,
      scrolling: Boolean(animation && animation.playState === "running"),
      rate: animation?.playbackRate || 0,
      copies: track.querySelectorAll(".ticker-sequence").length,
      still: root.classList.contains("still"),
      idle: idle.hidden ? "" : idle.textContent,
    }),
  };
  poller = VoidCompassOverlay.startPolling({
    token: params.get("token") || "", overlay: params.get("overlay") || "galnet-ticker",
    render, contentHeight: () => root.getBoundingClientRect().height || 34, interval: 250,
  });
})();
