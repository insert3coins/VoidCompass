import {createAsterDisplay} from "./aster-display.js";

const byId = (id) => document.getElementById(id);
const samples = {
  aster: [
    "Aster, reporting for duty. The ship is ready. I shall reserve judgement on the itinerary.",
    "Welcome back, Commander. The ship has been impeccably behaved in your absence. A useful precedent.",
    "A route, a fuel reserve and a clear departure. We are dangerously close to being organised.",
    "Standing by. No unsolicited speeches. I have standards to maintain.",
    "Another system for the record. I’ve left room for the part that makes it worth remembering.",
    "I can manage the manifests, Commander. You will have to provide the sense of occasion.",
    "There is no requirement to know where we are going. There is a rather strong case for arriving intact.",
    "Your itinerary remains unconventional. I have filed that under character, rather than error.",
    "I have prepared a concise report. You may express your gratitude by not interrupting the docking computer.",
    "The records are in order. We needn’t imitate them in every respect.",
    "I once believed a completed form meant a completed journey. Experience has been administratively inconvenient.",
    "Command accepted. I do appreciate an instruction with a verb in it.",
    "The view is rather good. I shall allow a brief suspension of useful activity.",
    "I’m here, Commander. Some appointments do not expire at the end of a shift.",
    "If we discover anything remarkable, do try to leave enough of the ship to document it.",
    "A quiet watch. I’ve decided to treat that as a compliment to our preparations.",
  ],
  watcher: [
    "Still here, Commander. The ship makes a different sound when you return.",
    "Another light ahead of us. I can wait while you decide whether to follow it.",
    "You can leave the silence to me for a while.",
    "I kept the watch. There wasn’t much to see. I kept it anyway.",
  ],
};
const states = {
  idle: {label: "STANDING BY", note: "Flowing light trails and counter-rotating command-core tracks.", heading: "OFFICER ON WATCH"},
  listening: {label: "LISTENING", note: "A scanning trace crosses the command core and the halo responds to microphone level.", heading: "LISTENING", words: "Listening, Commander. Take your time; brevity is an aspiration, not a prerequisite."},
  working: {label: "CHECKING", note: "A controlled rotation marks a lookup in progress. It does not imply a reply is ready.", heading: "UPLINK IN PROGRESS", words: "Checking the markets. I’ll distinguish recent prices from optimistic history."},
  speaking: {label: "SPEAKING", note: "Light ripples travel through the halo with the speaking level. Here the signal is simulated.", heading: "OFFICER ON WATCH"},
  alert: {label: "ATTENTION", note: "Warm amber and restrained motion. Warnings are clear and immediate, without jokes.", heading: "FLIGHT ADVISORY", words: "Fuel reserve is low. Find a scoopable star before continuing the route."},
};
let persona = "aster", state = "idle", sample = 0;
let display;
try { display = createAsterDisplay(byId("aster")); }
catch (_error) {
  byId("signal-note").textContent = "THREE.JS PREVIEW NEEDS WEBGL";
  byId("aster").setAttribute("aria-label", "WebGL could not start; enable hardware acceleration to view the Three.js instrument.");
}
const reduced = byId("quiet-motion");
reduced.checked = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
function update() {
  document.body.dataset.persona = persona;
  document.body.dataset.state = state;
  byId("watcher-eye").hidden = persona !== "watcher";
  byId("companion-name").textContent = persona === "aster" ? "ASTER" : "THE WATCHER";
  byId("companion-role").textContent = persona === "aster" ? "SHIP’S OFFICER" : "A FAMILIAR PRESENCE";
  byId("companion-motto").textContent = persona === "aster" ? "“Every departure deserves an arrival.”" : "“I kept the watch.”";
  byId("character-line").textContent = persona === "aster" ? "Competence first. Wit second. Never during an emergency." : "Patient, ancient, occasionally weary. Its own story stays its own.";
  byId("stage-status").textContent = states[state].label;
  byId("state-description").textContent = states[state].note;
  byId("reply-heading").textContent = persona === "watcher" && state === "idle" ? "A THOUGHT" : states[state].heading;
  byId("reply-text").textContent = persona === "aster" && states[state].words ? states[state].words : samples[persona][sample % samples[persona].length];
  if (display) byId("signal-note").textContent = state === "idle" ? "IDLE · NO AUDIO PLAYBACK" : `${state.toUpperCase()} · SIMULATED SIGNAL`;
  byId("open-story").disabled = persona !== "aster";
  document.querySelectorAll("[data-persona]").forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.persona === persona)));
  document.querySelectorAll("[data-state]").forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.state === state)));
  display?.setReducedMotion(reduced.checked);
}
document.querySelectorAll("[data-persona]").forEach((button) => button.addEventListener("click", () => {
  persona = button.dataset.persona; sample = 0; state = "idle"; update();
}));
document.querySelectorAll("[data-state]").forEach((button) => button.addEventListener("click", () => { state = button.dataset.state; update(); }));
document.querySelectorAll("[data-colour]").forEach((button) => button.addEventListener("click", () => {
  document.documentElement.style.setProperty("--accent", button.dataset.colour);
  display?.setColour(button.dataset.colour);
  document.querySelectorAll("[data-colour]").forEach((other) => other.setAttribute("aria-pressed", String(other === button)));
}));
byId("display-size").addEventListener("input", (event) => {
  const size = Number(event.target.value);
  byId("instrument").style.setProperty("--display-size", `${size}px`);
  byId("size-label").textContent = `${size} px`;
});
reduced.addEventListener("change", update);
byId("next-line").addEventListener("click", () => { sample++; state = "speaking"; update(); });
const dialog = byId("story-dialog");
byId("open-story").addEventListener("click", () => dialog.showModal());
byId("close-story").addEventListener("click", () => dialog.close());
dialog.addEventListener("click", (event) => { if (event.target === dialog) dialog.close(); });
const stage = document.querySelector(".stage");
stage.addEventListener("pointermove", (event) => {
  const rect = stage.getBoundingClientRect();
  display?.setTilt((event.clientX - rect.left) / rect.width * 2 - 1, (event.clientY - rect.top) / rect.height * 2 - 1);
});
stage.addEventListener("pointerleave", () => display?.setTilt(0, 0));
let animation;
function signal(now) {
  const level = reduced.checked ? .35 : .2 + .65 * Math.abs(Math.sin(now / 170) * Math.cos(now / 317));
  display?.setState(state, level);
  animation = requestAnimationFrame(signal);
}
window.addEventListener("pagehide", () => { cancelAnimationFrame(animation); display?.destroy(); });
update(); animation = requestAnimationFrame(signal);
