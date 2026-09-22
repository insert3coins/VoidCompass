import {BOOT_FACTS} from './boot-facts.js';

const boot = document.getElementById('boot');
const loader = document.getElementById('boot-loader');
const companion = document.querySelector('.boot-companion');
const current = document.getElementById('boot-fact');
const previous = document.getElementById('boot-fact-previous');
let deck = [], lastId = '', timer = 0, voiceTimer = 0;
const active = () => !document.hidden && !boot.hidden && !loader.hidden
  && !document.body.classList.contains('ready');

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
  if (!active()) {
    clearInterval(timer);
    clearTimeout(voiceTimer);
    timer = voiceTimer = 0;
    companion.classList.remove('speaking');
  } else if (!timer) {
    if (!current.textContent) nextFact();
    timer = setInterval(nextFact, 9000);
  }
}
const observer = new MutationObserver(sync);
for (const node of [boot, loader, document.body]) {
  observer.observe(node, {attributes: true, attributeFilter: ['hidden', 'class']});
}
document.addEventListener('visibilitychange', sync);
window.addEventListener('pagehide', () => {
  clearInterval(timer);
  clearTimeout(voiceTimer);
  observer.disconnect();
  document.removeEventListener('visibilitychange', sync);
}, {once: true});
sync();
