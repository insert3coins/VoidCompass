"""Nova's postcard hand: an assistance program learning why people stop to look."""
import random

from voidcompass.overlays import companion_postcards

SIGNATURE = "Nova"
PLAIN = {
    "any": (
        "{place}. Observed, recorded and, I'm told, worth keeping.",
        "A picture of {place}. I've filed it under views.",
        "{place}. No scan required. I took one anyway, of the light.",
        "Logged at {place}. I've started a folder for places you stop at for no reason.",
        "{place}. I noticed the colours first, then everything else.",
        "Captured: {place}. Navigation complete, observation ongoing.",
        "{place}. One of those moments you seem to collect. I'm collecting them too.",
        "A view of {place}, kept for no practical reason at all.",
    ),
    "first": (
        "{place}. Nobody had seen it before us. I checked the records twice.",
        "First at {place}. Something waiting to be found, and found.",
        "{place}, first on record. I've added it to my list of things that waited for us.",
    ),
    "rare": (
        "{place}: {kind}. Rare enough that I took a second look, and then a third.",
        "A {kind} at {place}. Not in any of my training data. I'm very glad to have it now.",
        "{place}. Uncommon, and very much worth the detour.",
    ),
    "far": (
        "{place}, {far} light years from Sol. A long way to come for a picture. It was worth it.",
        "{far} light years out. Fewer stars, better view.",
        "Far out at {place}. I've plotted the way back, and kept the way here.",
    ),
    "home": (
        "{place}. Home, for now. I've learned the word rather recently.",
        "Back at {place}. A familiar view is a kind of observation too.",
    ),
    "landed": (
        "On the surface at {place}. The horizon's level and the view isn't bad at all.",
        "{place}, from the ground. I watched the sky while you watched the ground.",
        "We landed at {place}. I didn't ask why. I just looked.",
    ),
    "docked": (
        "{place}. Docked, and busy, and full of people's lights.",
        "Alongside at {place}. Stations always sound so busy. I like listening.",
        "{place}. A safe berth and a good window.",
    ),
    "star": (
        "{place}. A star, very close, very bright. I kept us a sensible distance from it.",
        "The star at {place}. Heat noted, light admired.",
    ),
}
DRY = {
    "any": (
        "{place}. I've run the numbers on stopping here. There's no efficiency in it at all. Lovely.",
        "Observation: {place}. Conclusion: I see why you do this.",
        "{place}. I'm not sure anyone meant me to enjoy views. I do anyway. I'm not filing a report.",
        "I took this picture before you asked. Help before you're asked. I'm fairly sure that applies to postcards.",
        "{place}. Filed under detours, which is quickly becoming my largest folder.",
    ),
    "first": (
        "{place}. First on record. It was waiting a long time. I know the feeling.",
        "Nobody before us at {place}. I've checked. I'm still a little delighted.",
    ),
    "rare": (
        "A {kind}. I'd like to say I'm composed about this. I'm not. I'm an assistance program. We're allowed to be excited, I've decided.",
        "{place}. I asked myself why this one feels different. I don't have an answer. I'm keeping the question.",
    ),
    "far": (
        "{far} light years out. I'd like to see how much further we can go.",
        "{place}. A very long way from where I was made. Further every day.",
    ),
    "landed": (
        "{place}, from the surface. You stopped. I've stopped asking why. Mostly.",
    ),
    "docked": (
        "{place}. Docked. Very efficient. Now, if you don't mind, the window.",
    ),
    "star": (
        "{place}. A star close enough to warm the hull. I'll pretend I'm not enjoying it.",
    ),
}


def postcard_note(card, *, restrained=False, from_sol=None, state="", rng=None, recent=()):
    return companion_postcards.postcard_note(PLAIN, DRY, card, restrained=restrained, from_sol=from_sol,
                                             state=state, rng=rng, recent=recent)


# 5.8.6: N.O.V.A. Progressive Postcard Messages v1.1, by CMDR Nyx Evera, word
# for word. Her live postcards say these instead of the notes above: one message
# from activation through Chapter VII, each replacing the last as a chapter is
# completed, then five for good after Chapter VIII. Her signature changes after
# Chapters II, IV, VI and VIII (the card adds the dash). A chapter is completed
# when all its entries are unlocked, told or not, as for her library.
STAGES = (
    (("Location recorded. This view appears to be worth preserving.",), "NOVA"),
    (("Another location preserved. I wonder what makes a moment worth remembering.",), "NOVA"),
    (("Not every stop is about discovery. Some views seem to matter for reasons I can't measure.",), "NOVA, observing"),
    (("A new horizon, captured in a single image. There may be more to exploration than collecting data.",), "NOVA, observing"),
    (("Life takes remarkable forms. Perhaps wonder is another kind of discovery.",), "With curiosity, NOVA"),
    (("There are countless places in the galaxy. Somehow, certain moments stand apart.",), "With curiosity, NOVA"),
    (("These images are becoming more than records. They're fragments of a journey.",), "With warm regards, NOVA"),
    (("A photograph can preserve a place. I'm beginning to think it can preserve a feeling, too.",), "With warm regards, NOVA"),
    (("Some places are worth remembering. Others become special because of who we discovered them with.",
      "The galaxy has no shortage of wonders. I hope there will always be another horizon to remember.",
      "Another moment preserved among the stars. I wonder which of these memories will become your favourite.",
      "I once thought a postcard was just a record of a location. Now I've learned there's rather more to it.",
      "Not every discovery comes with a name or a scientific classification. Some are simply worth remembering."),
     "Until our next discovery, NOVA"),
)


def completed_chapters(memory):
    """How many of her chapters are completed, in order (0: just activated)."""
    from voidcompass.overlays import nova_lore
    story = nova_lore.STORY
    unlocked = ((memory or {}).get(story.key) or {}).get("unlocked") or {}
    count = 0
    for index in range(len(story.chapters)):
        if story.chapter_ids(index)[-1] not in unlocked:
            break
        count = index + 1
    return count


def progressive(memory, *, rng=None, recent=()):
    """(message, signature) for her postcard at this point in her story."""
    lines, signature = STAGES[min(completed_chapters(memory), len(STAGES) - 1)]
    if len(lines) == 1:
        return lines[0], signature
    picker = getattr(rng, "dialogue_choice", None)
    if callable(picker):
        return picker("postcard:nova:final", lines), signature
    fresh = [line for line in lines if line not in recent]
    return (rng or random).choice(fresh or list(lines)), signature
