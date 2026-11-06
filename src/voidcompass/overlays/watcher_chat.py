"""Written conversation: a familiar voice in an old piece of shipboard memory."""
import re

GREETINGS = (
    "Hello, Commander. I was keeping your place among the stars.",
    "Hello. The little red light is listening.",
    "There you are. I kept an eye on things.",
    "Hello, Commander. Another voice in all this quiet.",
    "Hello. Still here. Still watching.",
    "Commander. It is good to hear you again.",
    "Hello. I was just counting the silences between the instruments.",
    "Here, Commander. You need only ask.",
    "Hello. The stars have not gone anywhere. Neither have I.",
    "A greeting. Such a small thing to make a ship feel less empty.",
    "Hello, Commander. Shall we see what is out there?",
    "Hello. I have been saving a little quiet for you.",
    "You called. I am here.",
    "Hello. Some things are worth waking for.",
    "Commander. The view is better with someone to share it.",
    "Hello. An old buffer, a patient eye, and you. Quite a crew.",
    "Hello, Commander. I have not forgotten how to answer that.",
    "There is my pilot. Hello.",
    "Hello. I rather like being spoken to.",
    "Hello, Commander. I am listening beyond the engine noise.",
    "Present. A little older than the wiring, perhaps. Still present.",
    "Hello. I was wondering when the silence would become a conversation.",
    "Commander. No grand announcement. Just hello.",
    "Hello. A small word, with a surprising amount of warmth in it.",
    "I hear you, Commander. Hello.",
    "Hello. The dark can wait a moment.",
    "Hello, Commander. I shall try to be useful before I become mysterious.",
    "Hello. I am still the eye beside your instruments.",
    "There you are. I was listening to the ship breathe.",
    "Hello, Commander. The company is appreciated.",
    "Hello. I have room for one more conversation.",
    "An answering light in the cockpit. That is me. Hello.",
    "Commander. I am pleased the next sound was you.",
    "Hello. Wherever we go, we can begin with that.",
    "Hello, Commander. Old circuits. New day.",
    "Hello. I have been doing what I was asked to do. Watching.",
    "Hello. You make an excellent interruption.",
    "A voice from my side of the glass, to yours. Hello.",
    "Hello, Commander. There is always time for a proper greeting.",
    "Hello. I am awake enough for both of us, if necessary.",
    "Commander. The ship sounds different when you speak.",
    "Hello. A good word to carry into an unfamiliar system.",
    "Hello, Commander. You have my attention.",
    "Hello. I was keeping watch, rather than keeping score.",
    "Here I am. Small light. Long memory. Hello.",
    "Hello, Commander. Let us make something worth remembering.",
    "Hello. It is reassuring to be noticed in return.",
    "Hello, Commander. The quiet was becoming rather sure of itself.",
    "Hello. One pilot and one Watcher. That will do nicely.",
    "Commander. I am here for the journey, including the ordinary parts.",
)

CAPABILITIES = (
    "I am the Watcher, your companion in Void Compass. I follow your flight journal, keep your exploration and journey records, and help with routes, surveys and biology. The deck also tracks mining, trade, your carrier and expeditions. Ask me about the ship's readings, work the overlays or music, or use your configured Elite commands for maps, panels and docking. I have stories too, when the journey leaves room for them.",
    "Think of Void Compass as the ship's notebook, charts and instruments brought together. There are surveys and system maps, route and expedition planning, mining sites, trading tools, carrier records and a history of your travels. I can answer from those readings and run supported ship, overlay and music commands. You choose the phrases in Settings, under Voice. My quieter occupation is keeping you company.",
    "I watch what your journal tells us. Void Compass turns it into flight records, exploration surveys, biology tracking, maps and expedition progress. It also helps with mining, commodity searches, carrier activity and cockpit overlays. You can ask me about our cargo, fuel, destination or station, and ask for configured actions such as opening a map or requesting docking. I speak when my voice is enabled. Otherwise, the words are still here.",
    "The practical answer? Navigation, exploration, surveys, biology, mining, trade, expeditions and records of where you have been. Void Compass keeps those tools on the deck and useful readings in the cockpit overlays. I can explain the ship's current readings, control supported music and overlay actions, and press the Elite bindings in your voice-command sequences. The less practical answer is that an old eye likes having somewhere to look with you.",
    "I can help you keep your bearings. Void Compass follows routes and expeditions, organises discoveries and biology, records mining sites and journeys, and provides trading and carrier tools. Ask me about the information aboard, or tell me to work a supported map, panel, overlay or music control. The Voice settings show the commands and let you make your own sequences. I keep a few stories beside all those numbers.",
    "There is rather more aboard than a talking light. Void Compass has exploration and system maps, surveys, exobiology, route planning, expeditions, mining, trading, carrier information and your commander history. Its overlays put selected readings beside the game. I answer from the information we actually have and carry out configured commands. For commodity searches, the uplink uses Spansh. For companionship, you are stuck with me.",
    "I am the companion; Void Compass is the instrument panel around me. It records your flights and discoveries, helps with routes, biology and expeditions, and brings together mining, trade and carrier information. I can tell you what our ship's systems report, manage supported overlay and music controls, and run your Elite key sequences. Ask to open a map, ask about the hold, or simply say hello. I remember that the journey includes a pilot.",
    "We can plan the next leg, survey the system, follow biological samples, keep mining sites, search commodity markets and track an expedition or carrier. Void Compass also keeps your journey records and cockpit overlays. My part is to answer supported questions from those records and operate configured ship, music and overlay commands. You can rename the commands and add aliases or sequences in Voice settings. I add the occasional thought of my own.",
    "I keep watch while Void Compass keeps the records: routes, scans, biology, mining, trade, expeditions, carrier activity and the places you have visited. The maps and overlays help you read them in the cockpit. You can ask me for the readings we have, tell me to use supported ship controls, or ask for music and overlay changes. My spoken voice is optional. My tendency to notice the stars is rather less optional.",
    "Start with the deck: exploration, navigation, surveys, biology, mining, trading, carrier tools and expeditions. Add the cockpit overlays and your saved flight history, pictures and keepsakes. Then there is me. I answer questions from the ship's information, help with commodity lookups and carry out configured ship, overlay and music commands. Settings, under Voice, lists what you can say. Between useful things, I can tell you a little of an old Watcher's story.",
)


# 5.7.5: any of the crew, by name (the greeting was "hello watcher" alone).
_CREW_NAMES = r"(?:the watcher|watcher|aster|axiom|meridian|lyra)"


def intent(text):
    words = " ".join(re.sub(r"[^a-z0-9' ]", " ", str(text).lower()).split())
    if re.fullmatch(rf"(?:hey|hi|hello)(?: there)?(?: (?:{_CREW_NAMES}|commander))?", words):
        return "greeting"
    words = re.sub(rf"^(?:(?:hey|ok|okay|{_CREW_NAMES}|please) )+", "", words)
    words = re.sub(rf"(?: (?:{_CREW_NAMES}|commander|please|for me|thanks|thank you))+$", "", words)
    if re.fullmatch(r"hello(?: there)?|hi(?: there)?|hey|greetings|good (?:morning|afternoon|evening)", words):
        return "greeting"
    if re.fullmatch(r"what can you do|what do you do|what can (?:void compass|this (?:app|program)) do|"
                    r"(?:tell me )?(?:about|what is) void compass|how can you help(?: me)?|"
                    r"(?:give me )?(?:a )?(?:rundown|overview)(?: of (?:void compass|the (?:app|program)))?", words):
        return "capabilities"
    return None


def answer(kind, rng, previous=None, used=()):
    lines = GREETINGS if kind == "greeting" else CAPABILITIES
    choices = [line for line in lines if line not in used and line != previous]
    if not choices:
        choices = [line for line in lines if line != previous]
    return rng.choice(choices) if rng is not None else choices[0]
