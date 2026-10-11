"""The Watcher's words for time capsules and On this day (5.5.3.7).

A capsule is handed back in your own words: {note} is what you wrote, {span}
how long it waited, {system} where. On this day: {ago} ("a year ago", "3
years ago") and {system}, where that day began.
"""

CAPSULE_NORMAL = (
    'You left something here {span} ago. You wrote: "{note}"',
    'A note from you, sealed in {system} {span} ago: "{note}"',
    'I kept this for you. {span} ago, you wrote: "{note}"',
    'Your own words, waiting here for {span}: "{note}"',
    '{system} has held this for {span}. It\'s yours: "{note}"',
    'A time capsule, Commander. From you, {span} ago: "{note}"',
    'You told me to give you this when you came back. {span} later: "{note}"',
    'Back in {system}. You left a note for this moment: "{note}"',
    'Something you wanted to remember, {span} ago: "{note}"',
    'Here it is, as you left it {span} ago: "{note}"',
    'The note you sealed here has waited {span}. It says: "{note}"',
)

CAPSULE_WEARY = (
    'You left a note here {span} ago. I held onto it. Someone had to. "{note}"',
    '{span} I carried this. Here. Your words, not mine: "{note}"',
    'A capsule. From you, {span} ago. I didn\'t read it. Much. "{note}"',
    '{system} waited {span} to give you this. So did I: "{note}"',
    'You came back. Most don\'t. You left this {span} ago: "{note}"',
    'Your note, {span} old. It has aged better than I have: "{note}"',
    'I was told to hand you this here. {span} of waiting. "{note}"',
    'Back in {system}, then. You wrote this {span} ago, before you knew better: "{note}"',
    'Something from the past. Yours, for once, not mine: "{note}"',
    '{span}. That\'s how long this sat in the dark for you: "{note}"',
    'The note you sealed here. I kept it dry. Metaphorically. "{note}"',
)

ON_THIS_DAY_NORMAL = (
    "{ago} today, you were in {system}.",
    "On this day, {ago}, you were at {system}.",
    "{ago} today: {system}. I remember it.",
    "This day, {ago}, began in {system}.",
    "A year turns. {ago} today, {system}.",
    "{ago}, on this very date, you woke up in {system}.",
    "Do you remember {system}? {ago} today.",
    "On this day, {ago}: {system}, and the jumps that followed.",
    "{ago} today your day started at {system}. Look where you are now.",
    "The log says {system}, {ago} today.",
)

ON_THIS_DAY_WEARY = (
    "{ago} today you were in {system}. It felt further then.",
    "On this day, {ago}: {system}. I remember the quiet.",
    "{ago}, today, {system}. You were younger. So was I, probably.",
    "{system}, {ago} today. Same stars. Different us.",
    "This date, {ago}: {system}. Nothing has changed. Everything has.",
    "{ago} today we were at {system}. I wasn't counting. I was.",
    "On this day, {ago}, {system}. I'd tell you it was better then. It wasn't.",
    "{ago} today: {system}. Time passes even out here. Mostly on me.",
    "You were in {system} {ago} today. I thought you'd want to know. Or not.",
    "{system}, on this date, {ago}. I keep these things. Nobody else does.",
)

# A capsule here that isn't ready ("Not before…"): {system}, and {wait},
# how long until it opens ("3 weeks", "a day").
CAPSULE_EARLY_NORMAL = (
    "There's something here for you. Not yet, though. It opens in {wait}.",
    "You left a capsule in {system}, and told it to wait. {wait} to go.",
    "I can see your note from here. You sealed it for later: another {wait}.",
    "A capsule, still sealed. You asked it to wait. Come back in {wait}.",
    "Something of yours is waiting in {system}. It isn't time. Give it {wait}.",
    "Your capsule knows you're here. It won't open for another {wait}.",
    "Not yet. The note you left here opens in {wait}.",
    "You're early. The capsule in {system} has {wait} left to wait.",
    "I'll keep holding it. Your note here opens in {wait}.",
    "Sealed for later, by you. Later is {wait} away.",
)
CAPSULE_EARLY_WEARY = (
    "There's a note here. You told it to wait. It's better at waiting than you. {wait} more.",
    "You're early. Of course you are. The capsule opens in {wait}.",
    "I could open it. I won't. You said wait. {wait} to go.",
    "Something sealed in {system}. Another {wait} of patience, apparently.",
    "Your past self left instructions: not for another {wait}. I follow instructions.",
    "It's there. It's yours. It's not time. {wait} more.",
    "Back too soon. The note here opens in {wait}. I'll hold it. Again.",
    "You sealed it for later. This isn't later. Later is {wait} away.",
    "A capsule, still asleep. {wait} until it wakes. I know the feeling.",
    "I can feel it waiting in {system}. {wait} left. Don't ask me to peek.",
)

# A constellation finished: {name}, {count} stars.
CONSTELLATION_NORMAL = (
    "{count} stars. That's a constellation now. I've called it {name}.",
    "Your sky has a new shape. {name}.",
    "Another constellation, finished. {name}, if you'll let me name it.",
    "The last star is in place. I'm calling it {name}.",
    "{name}. {count} places you stayed, joined up at last.",
    "You finished one. {name}. It's on your Constellation page.",
    "There's a new shape in your sky tonight: {name}.",
    "Every navigator gets a constellation. You have another: {name}.",
    "{count} stars, one name. {name}.",
    "I traced the lines myself. {name}. Go and look.",
)
CONSTELLATION_WEARY = (
    "{count} stars. A constellation. I named it {name}. Nobody asked me to.",
    "Your sky got a new shape. {name}. It looks like something, if you squint.",
    "Finished one. {name}. The galaxy didn't notice. I did.",
    "{name}. {count} times you stopped long enough for me to count.",
    "Another constellation. {name}. I'd frame it, if I had walls.",
    "The last star went in. {name}. I'm told that's an accomplishment.",
    "{name}. That's what I'm calling it. You can argue. You won't.",
    "{count} stars, joined up. {name}. It'll outlast us both.",
    "A new shape in the dark: {name}. I spent too long on the name.",
    "{name}. Done. On to the next one, I suppose. There's always a next one.",
)
