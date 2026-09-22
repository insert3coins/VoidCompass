import {BOOT_FACTS} from './boot-facts.js';

const boot = document.getElementById('boot');
const loader = document.getElementById('boot-loader');
const companion = document.querySelector('.boot-companion');
const current = document.getElementById('boot-fact');
const previous = document.getElementById('boot-fact-previous');
const lens = companion.querySelector('.boot-optic-lens');
const waves = [...companion.querySelectorAll('.boot-activity-wave')];
const motion = matchMedia('(prefers-reduced-motion: reduce)');
let activityTimer = 0, activityAnimations = [], lastActivity = -1;
const reduced = () => motion.matches || document.body.classList.contains('reduced-motion');
let deck = [], lastId = '', timer = 0, voiceTimer = 0;
const active = () => !document.hidden && !boot.hidden && !loader.hidden
  && !document.body.classList.contains('ready');

function stopActivity() {
  clearTimeout(activityTimer);
  activityTimer = 0;
  activityAnimations.forEach(animation => animation.cancel());
  activityAnimations = [];
}

function playActivity() {
  activityTimer = 0;
  if (!active() || reduced()) return;
  activityAnimations.forEach(animation => animation.cancel());
  // Decorative activity only; never touches journal state or boot progress.
  const variant = (lastActivity + 1 + Math.floor(Math.random() * 2)) % 3;
  lastActivity = variant;
  const palette = getComputedStyle(loader);
  const colour = palette.getPropertyValue(['--accent', '--green', '--orange'][variant]).trim() || '#00d1ff';
  const resting = getComputedStyle(lens).color;
  const x = (Math.random() - .5) * 5, y = (Math.random() - .5) * 5;
  const duration = 1300 + Math.random() * 400;
  activityAnimations = [lens.animate([
    {transform: 'translate(0,0) scale(1)', filter: 'brightness(1)', color: resting},
    {transform: `translate(${x}px,${y}px) scale(.96)`, filter: 'brightness(1.4)', color: colour, offset: .25},
    {transform: `translate(${x}px,${y}px) scale(1.035)`, filter: 'brightness(1.15)', color: colour, offset: .45},
    {transform: 'translate(0,0) scale(1)', filter: 'brightness(1)', color: resting},
  ], {duration, easing: 'cubic-bezier(.22,.61,.36,1)'})];
  if (variant !== 1) waves.forEach((wave, index) => {
    activityAnimations.push(wave.animate([
      {transform: 'scale(.95)', opacity: 0, color: colour},
      {transform: 'scale(1.2)', opacity: .5, color: colour, offset: .25},
      {transform: 'scale(1.85)', opacity: 0, color: colour},
    ], {duration: 1100, delay: index * 230, easing: 'ease-out'}));
  });
  activityTimer = setTimeout(playActivity, duration + 1100 + Math.random() * 2100);
}

function nextFact() {
  if (!active() || !BOOT_FACTS.length) return;
  if (!deck.length) {
    deck = [...BOOT_FACTS];
    for (let i = deck.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [deck[i], deck[j]] = [deck[j], deck[i]];
    }
    if (deck.length > 1 && deck.at(-1).id === lastId) [deck[0], deck[deck.length - 1]] = [deck.at(-1), deck[0]];
  }
  const fact = deck.pop();
  previous.textContent = current.textContent;
  previous.hidden = !previous.textContent;
  current.textContent = fact.text;
  current.dataset.factId = fact.id;
  lastId = fact.id;
  companion.classList.add('speaking');
  clearTimeout(voiceTimer);
  voiceTimer = setTimeout(() => companion.classList.remove('speaking'), 1800);
}

function sync() {
  if (!active() || reduced()) stopActivity();
  else if (!activityTimer) activityTimer = setTimeout(playActivity, 600 + Math.random() * 600);
  if (!active()) {
    clearInterval(timer);
    clearTimeout(voiceTimer);
    timer = voiceTimer = 0;
    companion.classList.remove('speaking');
  } else if (!timer) {
    if (!current.textContent) nextFact();
    timer = setInterval(nextFact, 3000);
  }
}
const observer = new MutationObserver(sync);
for (const node of [boot, loader, document.body]) {
  observer.observe(node, {attributes: true, attributeFilter: ['hidden', 'class']});
}
document.addEventListener('visibilitychange', sync);
motion.addEventListener('change', sync);
window.addEventListener('pagehide', () => {
  stopActivity();
  clearInterval(timer);
  clearTimeout(voiceTimer);
  observer.disconnect();
  document.removeEventListener('visibilitychange', sync);
  motion.removeEventListener('change', sync);
}, {once: true});
sync();
