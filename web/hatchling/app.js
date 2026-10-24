(() => {
  "use strict";
  const params = new URLSearchParams(location.search);
  const token = params.get("token") || "";
  const overlay = params.get("overlay") || "hatchling";
  const dom = Object.fromEntries(["hatchling", "pet", "name", "title", "mood", "wants", "needs", "line"]
    .map((id) => [id, document.getElementById(id)]));
  // From html_hatchling_overlay.py: the width and least height the window is sized from.
  const DESIGN_WIDTH = 250, MIN_HEIGHT = 110;
  const NEEDS = [["hunger", ""], ["mood", "MOOD"], ["clean", "CLEAN"], ["health", "HEALTH"], ["energy", "SLEEP"]];
  let model = null;
  let needsKey = "";

  function node(tag, className = "", text = "") {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== "") element.textContent = String(text);
    return element;
  }

  function render(snapshot = {}) {
    const root = dom.hatchling;
    VoidCompassOverlay.applyTheme(root, snapshot.theme || {}, snapshot.effects || {});
    VoidCompassOverlay.fitToWindow(root, DESIGN_WIDTH, snapshot.effects || {});
    model = snapshot.hatchling || null;
    root.classList.toggle("empty", !model);
    if (!model) return;
    root.classList.toggle("low", Boolean(model.wants) || model.sick || model.dormant);
    dom.name.textContent = model.name.toUpperCase();
    dom.title.textContent = model.stage === "egg" ? "EGG" : `${model.title}${model.stage !== "adult" ? ` · ${model.stage.toUpperCase()}` : ""}`;
    dom.mood.textContent = model.stage === "egg" && model.hatch_minutes > 0 ? `HATCHES IN ${model.hatch_minutes} MIN` : model.mood_word;
    dom.wants.hidden = !model.wants;
    dom.wants.textContent = model.wants ? `WANTS ${model.wants}` : "";
    const key = JSON.stringify([model.needs, model.food_label, model.stage]);
    if (key !== needsKey) {
      needsKey = key;
      dom.needs.hidden = model.stage === "egg";
      dom.needs.replaceChildren(...NEEDS.map(([need, label]) => {
        const value = Math.max(0, Math.min(100, Number(model.needs?.[need]) || 0));
        const row = node("div", `need${value < 25 ? " low" : value < 50 ? " mid" : ""}`);
        const track = node("span", "track"), bar = node("i");
        bar.style.setProperty("--fill", `${value}%`);
        track.append(bar);
        row.append(node("small", "", label || model.food_label), track);
        return row;
      }));
    }
    dom.line.hidden = !model.line;
    dom.line.textContent = model.line || "";
  }

  // The pet moves on its own between snapshots.
  function animate() {
    const canvas = dom.pet;
    const ratio = window.devicePixelRatio || 1;
    const box = canvas.getBoundingClientRect();
    const width = Math.max(1, Math.round(box.width * ratio)), height = Math.max(1, Math.round(box.height * ratio));
    if (canvas.width !== width || canvas.height !== height) { canvas.width = width; canvas.height = height; }
    const ctx = canvas.getContext("2d");
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, width, height);
    if (model) {
      const size = Math.min(width, height);
      window.HatchlingArt.mess(ctx, model.mess || 0, width / 2, height / 2, size * .86);
      window.HatchlingArt.draw(ctx, model, {x: width / 2, y: height / 2, size: size * .86});
    }
    requestAnimationFrame(animate);
  }

  function contentHeight() {
    return VoidCompassOverlay.designHeight(dom.hatchling, MIN_HEIGHT);
  }

  requestAnimationFrame(animate);
  VoidCompassOverlay.startPolling({token, overlay, render, contentHeight, interval: 250});
})();
