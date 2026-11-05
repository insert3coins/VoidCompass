"""Axiom's postcard hand: an observation, entered with care."""
from voidcompass.overlays import companion_postcards

SIGNATURE = "Axiom"
PLAIN = {
    "any": (
        "{place}. Observation recorded. I have added a note that it was beautiful, with a narrow error bar.",
        "Entry: {place}. Observer: us. Conditions: excellent.",
        "I have catalogued this view of {place}. Some entries deserve a picture as well as a number.",
        "A photograph is a measurement taken for pleasure. This one was worth taking.",
        "Recorded at {place}. I compared this view with my expectations. The view was better.",
        "{place}, observed together. I will remember the light here.",
        "Not every observation needs a purpose. This one has one anyway: we were here.",
        "A small addition to the catalogue. A large one to mine.",
    ),
    "first": (
        "{place}. First on record. The catalogue now begins here, with us.",
        "Nobody had observed {place} before. I am glad the first observer was you.",
        "A first entry for {place}. I checked twice. It is still ours.",
    ),
    "rare": (
        "{place}: {kind}. Rare enough that I counted it three times to be sure.",
        "A {kind} at {place}. My old survey array saw a handful of these in twenty years. We came to look.",
        "{place}. An uncommon entry. I have marked it with a small star in my records. A real one would be confusing.",
    ),
    "far": (
        "{place}, {far} light years from Sol. Very few lights out here. We are one of them.",
        "{far} light years from where most people count. I have rarely felt so precisely located.",
        "Far out at {place}. The sky is sparse and the catalogue is honest. I like it here.",
    ),
    "home": (
        "{place}. Home again. Some entries are worth recounting.",
        "Back at {place}. Repeat observation. Result consistent: it is good to be here.",
    ),
    "landed": (
        "On the ground at {place}. The horizon is a long, unbroken line. I measured it. It was also lovely.",
        "{place}, from the surface. Gravity confirmed. View confirmed.",
        "We landed at {place}. I have catalogued the ground as well as the sky, for once.",
    ),
    "docked": (
        "{place}. Docked. Somewhere in this station's sky count, there is one extra light. It is us.",
        "Alongside at {place}. A busy, badly behaved sort of brightness. I approve.",
        "{place}: lights, people, noise. A great deal to count, and no need to.",
    ),
    "star": (
        "{place}. A star, observed rather too closely for comfort. A good photograph regardless.",
        "The star at {place} is extremely bright. I have adjusted my expectations and the exposure.",
    ),
}
DRY = {
    "any": (
        "{place}. I would explain why this is a good picture, but I have been told explanations spoil things.",
        "Observation: {place}. Conclusion: worth the detour. Confidence: higher than I usually allow myself.",
        "I have filed this under evidence that you have good taste in views.",
        "{place}. I attempted to quantify the view. The number did not do it justice. I have kept the picture instead.",
        "This photograph has no scientific value. I checked. It is staying in the catalogue anyway.",
    ),
    "first": (
        "{place}. First observation. I resisted the urge to name it after a footnote.",
        "Our name is on {place} now. I have practised saying it modestly.",
    ),
    "rare": (
        "A {kind}. I have made a note to be calm about it. The note is not working.",
        "{place}. A rare entry. I may have recounted it more times than strictly necessary.",
    ),
    "far": (
        "{far} light years out. The nearest catalogue is a very long way behind us. I find I do not miss it.",
        "{place}. Sparse sky, honest data, one ship. My kind of view.",
    ),
    "landed": (
        "{place}. I have confirmed that the ground is where the instruments said. It usually is. I still enjoy checking.",
    ),
    "docked": (
        "{place}. I tried to count the lights in this station. I stopped. It seemed rude to the people inside them.",
    ),
    "star": (
        "{place}. Very bright. I have recorded the brightness and also my opinion of it, which is favourable.",
    ),
}


def postcard_note(card, *, restrained=False, from_sol=None, state="", rng=None, recent=()):
    return companion_postcards.postcard_note(PLAIN, DRY, card, restrained=restrained, from_sol=from_sol,
                                             state=state, rng=rng, recent=recent)
