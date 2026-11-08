"""In the field (5.7.2): the Watcher says when you're the first, and how far
to go between biology samples.

First: the first world nobody had found in a system others have charted
(an undiscovered system has its own words, and a run of firsts too), the
first map of a world, and the first footsteps on one. The journal says so
in each world's Scan (WasDiscovered, WasMapped, WasFootfalled); FieldNotes
keeps what this system's scans said until you jump.

Samples: after the first and second sample of a species, how far the next
must be (its genus's colony range), and when you're far enough. These are
said from the written lines, keeping the measured distance.
"""
from __future__ import annotations
from voidcompass.core.discovery import footfall_open, new_ground, our_first

PLANET_FIRST_NORMAL = [
    "{body}. Nobody has charted that one before you.",
    "No one had found {body} until now. It's yours.",
    "{body} carries no one's name. It will carry yours.",
    "Others came through this system. None of them looked at {body}.",
    "First eyes on {body}. Yours.",
    "{body}: undiscovered until this moment.",
    "Every other world here had been seen. Not {body}.",
    "{body} was waiting for someone to look. You looked.",
    "The charts had nothing on {body}. They will now.",
    "A world no one had noticed: {body}. You noticed.",
]
PLANET_FIRST_WEARY = [
    "{body}. Nobody bothered with it before. We did. I suppose that's something.",
    "First to find {body}. It won't thank us, but it's ours.",
    "Others passed straight by {body}. Can't say I blame them. Still, it's yours now.",
    "{body}. Undiscovered. Like most things worth finding, it was easy to miss.",
    "No one had charted {body}. Your name goes on it. Mine never does.",
    "Hm. {body}, unclaimed until now. A small mercy.",
    "They flew past {body}. All of them. We didn't.",
    "{body} has waited a long time for anyone. It got us.",
    "First discovery: {body}. I'll try to feel something about it.",
    "Nobody's eyes before ours on {body}. That's rarer than it sounds.",
]
MAPPED_FIRST_NORMAL = [
    "{body} mapped. No one had mapped it before you.",
    "The first map of {body} is yours.",
    "Every line of {body}'s surface, drawn first by you.",
    "Nobody had mapped {body}. Now it's charted to the last ridge.",
    "First survey of {body}, done.",
    "{body}: mapped for the first time, and on record as yours.",
    "No probes had touched {body} before ours.",
    "The cartographers will see your name on {body}'s map.",
    "{body}, mapped. Nobody got there first.",
    "A first map. {body} won't be a blank any more.",
]
MAPPED_FIRST_WEARY = [
    "{body}, mapped. First one to bother. It shows.",
    "Nobody had mapped {body}. Now someone has. Us. Lucky {body}.",
    "First map of {body}. Every crater accounted for. I counted, out of habit.",
    "{body} mapped, first time. A little line in a big ledger.",
    "No one mapped {body} before us. Too dull for them, probably. Not for the record.",
    "The first probes ever to reach {body} were ours. They didn't come back. They never do.",
    "Mapped {body}. First. Put it on the pile of things only we've done.",
    "{body}: charted, first time. The galaxy is slightly less blank. Slightly.",
    "First to map {body}. I'll remember it. I remember everything.",
    "Hm. {body}, mapped before anyone else. That's worth a sigh. A good one.",
]
FOOTFALL_FIRST_NORMAL = [
    "First footsteps on {body}. Nobody has stood here before.",
    "You're the first person to walk on {body}.",
    "No boot has touched {body} before yours.",
    "{body}. First footfall. Take a moment.",
    "Nobody, ever, has stood where you're standing on {body}.",
    "The first footprints on {body} are yours.",
    "{body} has never felt a footstep. Until now.",
    "First person on {body}. Mind the step.",
    "Of everyone who ever lived, you're the first on {body}.",
    "First footfall on {body}. That one's for the records.",
]
FOOTFALL_FIRST_WEARY = [
    "First footprints on {body}. Nobody else wanted them. You do.",
    "You're the first to stand on {body}. It doesn't seem impressed. I am. A little.",
    "No one has walked on {body} before. Now one person has. Hm.",
    "{body}, first footfall. I'd come out and look, but I'm the ship.",
    "First on {body}. The ground has waited longer than anyone has lived.",
    "Nobody has stood here before. Not on {body}. Enjoy it. Someone should.",
    "The first steps on {body}. I'll keep the moment, in case you forget it.",
    "First person ever on {body}. That's a lonely sort of record.",
    "{body} has its first visitor. I'd have tidied, if I were {body}.",
    "First footfall. {body} will remember you. Well. I will.",
]
SAMPLE_FIRST_NORMAL = [
    "{species}, first sample. The next must be {distance} metres away.",
    "First of three for {species}. Move {distance} metres before the next.",
    "One sample of {species}. {distance} metres from here for the second.",
    "{species} logged. Find another at least {distance} metres off.",
    "That's one. The next {species} has to be {distance} metres away.",
    "First sample taken. {species} needs {distance} metres between samples.",
    "{species}: one in the sampler. The second, {distance} metres on.",
    "Sample one of {species}. Keep {distance} metres between you and it for the next.",
    "Logged. {species} wants its samples {distance} metres apart.",
    "The first {species} is in. Another, {distance} metres from this one.",
]
SAMPLE_FIRST_WEARY = [
    "One sample of {species}. Now go {distance} metres. They insist.",
    "{species}, first of three. The next one's {distance} metres off. Of course it is.",
    "That's one {species}. {distance} metres to the next. I'll count.",
    "First sample. {species} wants {distance} metres of room. Like everyone.",
    "{species} logged. {distance} metres before the next. The ground doesn't make it easy.",
    "One down. The next {species} must be {distance} metres away. No shortcuts.",
    "{species}, one sample. {distance} metres to the next. The walk does us good. Apparently.",
    "First of three {species}. Two more, and {distance} metres between each. Riveting.",
    "Sampled. Now {distance} metres of nothing before the next {species}.",
    "The sampler has one {species}. It wants another {distance} metres away. It always wants more.",
]
SAMPLE_SECOND_NORMAL = [
    "Second sample of {species}. One more, {distance} metres from both.",
    "Two of three. The last {species} must be {distance} metres from the others.",
    "{species}, two done. Get {distance} metres clear of both for the third.",
    "Nearly there. The final {species}: {distance} metres from both samples.",
    "Second {species} logged. The last one, {distance} metres from each.",
    "Two samples. One more {species}, at least {distance} metres from both.",
    "Sample two of {species}. The third must be {distance} metres from each of them.",
    "{species}: two in the sampler. One more, {distance} metres clear of both.",
    "Second done. Find the last {species} {distance} metres from the first two.",
    "Two {species} logged. The third, {distance} metres from either.",
]
SAMPLE_SECOND_WEARY = [
    "Two {species}. One more, {distance} metres from both. Nearly free.",
    "Second sample. The last {species} must be {distance} metres from both. Naturally.",
    "Two of three. {distance} metres clear of both, then we're done with {species}.",
    "{species}, twice. Once more, {distance} metres from both. I believe in you. Mostly.",
    "Second one logged. The third {species} wants {distance} metres from both.",
    "Two down. One {species} left, {distance} metres from the others.",
    "Second {species}. One more, {distance} metres from both, and then the analysis.",
    "Two of three {species}. The last one hides {distance} metres from both. They always do.",
    "Sample two. {distance} metres from both for the last {species}. Then rest.",
    "{species}, again. One more, {distance} metres from the others, and it's over.",
]
SAMPLE_CLEAR_NORMAL = [
    "Far enough: {distance} metres clear. The next {species} counts.",
    "You're clear of the last sample. Take the next {species} here.",
    "{distance} metres covered. The next {species} sample will count.",
    "Clear. Any {species} from here on counts.",
    "That's the distance. Sample the next {species} when you find one.",
    "Out of range of the last sample. {species} is fair game again.",
    "That's {distance} metres. The next {species} you sample will count.",
    "Clear of the colony. Sample {species} again.",
    "You're past {distance} metres. Go ahead with the next {species}.",
    "Far enough from the last one. {species}, whenever you're ready.",
]
SAMPLE_CLEAR_WEARY = [
    "Far enough. Any {species} from here counts. Go on.",
    "{distance} metres. We made it. The next {species} will count.",
    "Clear of the last sample. Find a {species}. Any {species}.",
    "That's the distance. Sample the next {species}, and we're one closer.",
    "Out of range now. The next {species} counts. Try not to pick the same one.",
    "Clear. {species} again, whenever you like.",
    "Past {distance} metres. The sampler will take the next {species}. Grudgingly.",
    "We're clear. Sample the next {species}. I'll wait. I'm good at waiting.",
    "{distance} metres behind us. The next {species} is worth sampling now.",
    "Far enough from the colony. {species}, once more. Or twice.",
]
BANKS = (
    ("planet_first", PLANET_FIRST_NORMAL, PLANET_FIRST_WEARY),
    ("mapped_first", MAPPED_FIRST_NORMAL, MAPPED_FIRST_WEARY),
    ("footfall_first", FOOTFALL_FIRST_NORMAL, FOOTFALL_FIRST_WEARY),
    ("sample_first", SAMPLE_FIRST_NORMAL, SAMPLE_FIRST_WEARY),
    ("sample_second", SAMPLE_SECOND_NORMAL, SAMPLE_SECOND_WEARY),
    ("sample_clear", SAMPLE_CLEAR_NORMAL, SAMPLE_CLEAR_WEARY),
)


class FieldNotes:
    """What this system's scans said about being first, until you jump."""

    def __init__(self):
        self.reset()

    def reset(self):
        # Whether anyone had charted the system (its arrival star's scan), the
        # worlds nobody had mapped or walked on, and whether a first world has
        # been remarked on here (once a system: the overlays list the rest).
        self.charted = None
        self.unmapped = set()
        self.unwalked = set()
        self.said_first = False

    def observe(self, event, raw):
        """Tracks the scans; ("mapped_first" | "footfall_first", fields) when it's so."""
        if event in ("FSDJump", "CarrierJump"):
            self.reset()
            return None
        if event == "Scan":
            body = str(raw.get("BodyName") or "")
            if raw.get("StarType") and not raw.get("DistanceFromArrivalLS"):
                self.charted = not our_first(raw)
            if raw.get("PlanetClass") and body:
                if raw.get("WasMapped") is False:
                    self.unmapped.add(body)
                if footfall_open(raw):
                    self.unwalked.add(body)
            return None
        if event == "SAAScanComplete":
            body = str(raw.get("BodyName") or "")
            if body in self.unmapped:
                self.unmapped.discard(body)
                return "mapped_first", {"body": body}
            return None
        if event == "Disembark" and raw.get("OnPlanet") and not raw.get("OnStation"):
            body = str(raw.get("Body") or "")
            if body in self.unwalked:
                self.unwalked.discard(body)
                if new_ground(raw):
                    return "footfall_first", {"body": body}
        return None

    def first_world(self, raw):
        """The first world nobody had found, in a system others have charted."""
        if self.charted and not self.said_first and raw.get("PlanetClass") and our_first(raw):
            self.said_first = True
            return True
        return False
