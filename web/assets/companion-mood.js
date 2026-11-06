// The mood of what a companion is saying, eased onto its display (5.7.6).
// Pleased, wary, downcast or curious from the thought on show; danger worries
// every companion whatever it is saying; listening makes it a little curious.
// The owning display supplies its clock: no timers or loop of its own.
const MOODS = {pleased:"joy", wary:"worry", downcast:"sad", curious:"curious"};

export function createMood() {
  let mood = "", state = "idle", settling = false;
  const expression = {joy:0, worry:0, sad:0, curious:0};
  function target() {
    const goal = {joy:0, worry:0, sad:0, curious:0};
    if (state === "alert") goal.worry = 1;
    else if (MOODS[mood]) goal[MOODS[mood]] = 1;
    else if (state === "listening") goal.curious = .6;
    return goal;
  }
  return {
    expression,
    // True when the display needs to draw to show the change.
    context(model) {
      const next = String(model?.thought?.mood || "");
      if (next === mood) return false;
      mood = next; settling = true; return true;
    },
    state(value) {
      if (value === state) return false;
      state = value; settling = true; return true;
    },
    // Reduced motion changes the face at once instead of easing.
    step(dt, reduced = false) {
      const goal = target(), rate = reduced ? 1 : 1 - Math.exp(-dt * 5);
      settling = false;
      for (const key in expression) {
        const next = expression[key] + (goal[key] - expression[key]) * rate;
        expression[key] = Math.abs(goal[key] - next) < .002 ? goal[key] : next;
        if (expression[key] !== goal[key]) settling = true;
      }
      return expression;
    },
    get settling() { return settling; },
    get mood() { return mood; },
  };
}
