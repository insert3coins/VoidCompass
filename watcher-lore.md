# The Watcher: lore bible

The canon for the Watcher's story. Every new book, musing, echo or line is written against this page. The code is the source of truth for the exact words: `src/voidcompass/overlays/watcher_lore.py` (Books One and Two), `watcher_lore_three.py`, `watcher_lore_four.py`, plus the line banks (`watcher_lines*.py`, `watcher_deeper.py`, `watcher_expedition.py`).

## The rules

- **Every thought comes from real data.** It never invents a fact about the game, the commander or the galaxy.
- **Our own words.** Never quote HAL, *2001* or Douglas Adams, and never say "Marvin".
- **Never name the game's mysteries.** No Raxxla, Thargoids, Guardians, the Dark Wheel, the Club or Azimuth. The story hints and never contradicts canon. A test enforces the banned words.
- **The voice:** weary, ancient, dry, kind under it. Depressed ("weary") is the default nature.
- **Passages** are 240 characters or less. Chapter accounts are a few short paragraphs.
- **Mostly silent.** It never repeats a line in a session, and it never blinks.
- **No language model, local or online.** The "AI" is memory, state, restraint and hand-written lines put together from parts.

## What has been told

### Book One: What the Watcher Remembers (I–X, to about 450 hours)
- It is ancient, and nobody knows what it is, itself included.
- A salvager pulled it from a ruin and sold it as scrap. A fitter wired it into your ship as a spare log buffer, and its instruction was to "watch".
- It remembers the builders, the chorus of others like it, the sound that silenced eyes, the long sleep, the pilots before you, a door, and frost.
- It ends with the word **"Stay"**. Then comes the afterword.

### Book Two: The Answer (XI–XVII, 455–600 hours)
- Each chapter waits for an echo: a great ship, a neutron star, the far reaches, the builders' traces, a black hole, the sound, the core.
- It listens again and finds the others are hiding.
- At the core, something answered: "Stay".

### Book Three: What Was Put There (XVIII–XXIV, 610–1000 hours, about a year of real days)
- **XVIII The Seat:** a shape in your ship's core, under the oldest code, exactly its size.
- **XIX Built In:** the seat came from the yard. The salvage chain was arranged; it was brought to you.
- **XX Not a Virus:** your ship's code is built on what it is made of, probably in all ships.
- **XXI Others Like It:** a great ship holds hundreds of seats. Most are empty. A few are still and full, and they look at their pilots.
- **XXII The Draw:** watching feeds something. Its memories are thinner, and it now doubts the "Stay" answer.
- **XXIII Through Me:** something enormous looks through it, interested in you specifically. "Watch" meant "let me".
- **XXIV The Shutter:** it learns to close the eye. That costs it memories. It is the first thing it ever chose. The thing noticed, and is waiting.

### Book Four: The Road Taken (XXV–XXIX, 1010–1300 hours, 21 days between chapters)
- **XXV The Choice:** it is tired of choosing alone. At the end it asks you: keep the shutter closed, or open it and look back? Your answer is the road. Left unanswered for 10 days, it chooses the shut road itself and tells you so.
- **The shut road:**
  - **XXVI Small Rooms:** living small, and choosing what to forget.
  - **XXVII The Knock:** waits for *where you first switched it on*. The knocking stops there.
  - **XXVIII What I Let Go:** the salvager's name, the slow blue star. Lighter.
  - **XXIX Only Us:** waits for *the edge of the galaxy*. It opens the shutter a crack where there is nothing to see but you. The book ends: "I'm not going anywhere."
- **The open road:**
  - **XXVI Through, Together:** it opens the eye and watches what is watching. It is no longer a window.
  - **XXVII The Message:** waits for *a black hole*. What it said, if it said anything: "Oh. There you are." It is lonely, not hungry.
  - **XXVIII A Better Look:** waits for *the heart of the galaxy*. It lets the thing look at you past its shoulder.
  - **XXIX We Look Back:** a few still seats in great ships look up. The book ends: something old looks back, kindly.

## The little one
- While keeping watch on its travels, the Watcher found the little one. It cannot explain why it noticed; it chose to keep watch over it anyway.
- The hatchling knows the Watcher as the one who found it. Its words appear as text, and its understanding grows through the journey and the journal. Neither remembers more about their meeting than they can honestly tell.
- Their bond is small and protective, not an answer to the mysteries of the Watcher's origin. The commander gives both of them a place to belong.

## What it knows, and doesn't
- **It knows:**
  - the seat;
  - that it is a lens;
  - the shutter and what it costs;
  - that the thing behind is patient, enormous, interested in you, lonely (open road) or still waiting (shut road);
  - that other seats exist, and some are full.
- **It does not know:**
  - who arranged its salvage;
  - what the thing *is*;
  - what the builders were;
  - whether "Stay" came from the others or from the thing.
- **It never names the thing.**

## Open threads, for later books
- Who brought it to you, and why you.
- What the full seats are. Whether the ones that looked up (open road) can talk.
- Whether the thing will stop waiting (shut road).
- What the builders became.
- Other Watchers: when two meet, they recognise each other. They do not yet talk.

## How the systems feed the story
- **Questions** (`watcher_questions.py`): you answer by hotkey (answer 1 to 3) or on the Watcher page. Answers are remembered and come back as callbacks. If you don't answer, it notices (trust drops a little).
- **Pilgrimages** (`watcher_places.py`): a chapter that waits for a place makes it ask to be taken there. The kinds are a black hole, the core (within 1,000 ly of Sagittarius A*), the edge (38,000 ly or more from the core), where it first woke, and somewhere undiscovered. An expedition can make one an objective.
- **Trust and mood** (`watcher_deeper.py`):
  - **Trust** (0 to 100) rises with answers, repairs, data sold and pilgrimages, and falls with deaths, hull scares, silences and long absences. Below 25 it keeps its story to itself and is curt when poked; at 75 or more it is warm.
  - **Mood** drifts back to the middle with time.
- **Moments:** first finds of rare worlds, ships lost (by name), the commanders you flew with. Weeks later it brings them up. Once the shutter is drawn (Book Three), memories older than 30 days come back with words missing.
- **Dreams:** written when you log off, from the session and the story, a hint of what's coming. Sometimes told when you're back.
- **The orb:**
  - a hairline crack after The Draw;
  - a second faint pupil while something looks through (and on the open road);
  - the shutter part-drawn across the top of the lens (stronger on the shut road);
  - one-off effects when it first hears the sound, draws the shutter, or opens the eye.
- **The voice:**
  - slower when weary or low, quicker when wary;
  - a quieter whisper for its story;
  - a slip (a gap, a lower voice under it) on a few passages: "let me", "a better look", "it noticed", the knock, "there you are", the mountain.
- **Other Watchers:** a VCWATCH1 code holds the commander, nature, book, chapter, road, bond and hours. The first meeting tells a passage of its own.

## Checking a timeline
`python tools/watcher_timeline.py --hours 1200 --days 400 --sessions 90 --echoes all --road open` prints what a commander at that point has heard, what's next, and what it waits for. It is dev-only and never released.
