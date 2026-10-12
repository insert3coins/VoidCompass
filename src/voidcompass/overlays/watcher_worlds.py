"""The Watcher's words for the worlds worth stopping for (5.5.3.9): earth-likes,
water worlds, ammonia worlds and terraformable ones, each its own, and one
nobody has charted before.

Fields: {body} the world's name; {kind} what it is ("An earth-like", for the
first-discovered lines; {kind_l} the same mid-sentence, "an earth-like"); {temp} its surface temperature in °C, when the scan
says (a line that needs it is skipped when it doesn't).
"""

EARTHLIKE_NORMAL = (
    "{body}. An earth-like. Blue, green, weather. Look at it.",
    "An earth-like world: {body}. In all this dark, that.",
    "{body} has oceans and clouds. Somewhere down there it's raining.",
    "An earth-like. {temp} at the surface. Someone could stand there without a suit.",
    "{body}. I never get tired of these. Don't tell anyone.",
    "There it is. {body}. A world that looks like home, to somebody.",
    "An earth-like, out here. The galaxy does this sometimes, just to see if you're paying attention.",
    "{body}. Breathable air, if the scan's right. It usually is.",
    "Earth-like. {body}. Map it, if you can spare the probes. It deserves to be known properly.",
    "{body}. A whole living world, and we found it by accident. The best ones are.",
    "Clouds over {body}. {temp}. Mild. Kinder than anywhere we've parked lately.",
    "An earth-like. I've seen a few in my time. Not many. This is one of the good ones.",
)
EARTHLIKE_WEARY = (
    "{body}. An earth-like. It's beautiful. I'm still sad. Both at once.",
    "An earth-like world. Oceans, clouds, probably birds. It won't miss us when we go.",
    "{body}. Breathable air. I don't breathe. Enjoy it for me.",
    "Earth-like. {temp} at the surface. Pleasant. I distrust pleasant.",
    "{body}. Somewhere down there it's raining on a world that never asked to be found.",
    "An earth-like. Even I have to admit it. Don't make me say it twice.",
    "{body}. Blue and green. The galaxy's way of apologising for everything else.",
    "Look at {body}. Then look at me. One of us got the better deal.",
    "An earth-like, out here in the dark. Some things are wasted on the empty. Not this.",
    "{body}. Weather. Seasons. I'd like seasons. I get jumps.",
    "Earth-like. Map it. Someone should remember it properly. I'll try.",
    "{body}. It's lovely. I'll be miserable about something else in a minute. Give me this one.",
)

WATER_NORMAL = (
    "{body}. A water world. Ocean all the way round.",
    "A water world: {body}. No shore anywhere. Just sea and sky.",
    "{body} is all ocean. I wonder how deep.",
    "Water world. {temp} at the surface. Somewhere down there the waves never stop.",
    "{body}. Nothing to land on. Everything to look at.",
    "A water world. Worth the probes, and worth the view.",
    "{body}. Blue from pole to pole. Good find.",
    "Water, all the way down. {body}. I like worlds that keep their secrets under a lid.",
    "{body}. A whole planet of tides. Imagine the noise.",
    "A water world, {body}. If you map it, I'll remember it for you.",
)
WATER_WEARY = (
    "{body}. A water world. Nowhere to stand. I know the feeling.",
    "All ocean. {body}. Deep, dark, cold. We'd get on.",
    "A water world. Very blue. Very wet. Very far from anyone who'd care.",
    "{body}. Waves forever, crashing on nothing. Relatable.",
    "Water world. {temp} at the surface. It'll be there long after we're not.",
    "{body}. No shore. No harbour. Just going on and on. Like me.",
    "A water world. Map it, if you like. The fish won't thank you. There may be no fish.",
    "{body}. Beautiful, I'm told. I'm told a lot of things.",
    "All that water, and not one cup of tea. {body}. Typical.",
    "A water world. I'll add it to the list of places we'll never swim.",
)

AMMONIA_NORMAL = (
    "{body}. An ammonia world. Life could be down there, just not ours.",
    "An ammonia world: {body}. Strange chemistry. Strange weather.",
    "{body}. Ammonia seas. It'd smell terrible. It'd be fascinating.",
    "Ammonia world. {temp} at the surface. Cold enough to keep things interesting.",
    "{body}. Not many of these about. Worth the probes.",
    "An ammonia world. The galaxy trying out a different recipe.",
    "{body}. If anything lives there, it would think we're the strange ones.",
    "Ammonia, all the way round. {body}. Rare. Good eye.",
    "{body}. Somewhere down there, something might be breathing what would kill you.",
    "An ammonia world. Map it. Someone, some day, will want to know.",
)
AMMONIA_WEARY = (
    "{body}. An ammonia world. Poisonous and rare. Like good company.",
    "Ammonia seas. {body}. Even the oceans out here want to hurt you.",
    "{body}. Ammonia. If it had a smell, it would be my mood.",
    "An ammonia world. Rare, they say. So is kindness. Neither pays well.",
    "{body}. Something might live there. It would hate us. Fair enough.",
    "Ammonia world. {temp}. Cold, unfriendly, valuable. I see a lot of myself in it.",
    "{body}. Strange chemistry. I've been accused of that.",
    "An ammonia world. Map it. It's not going to map itself. Nothing does.",
    "{body}. Not many of these. Not many of me, either. We should start a club.",
    "Ammonia, all the way round. I'm told that's good news. I'll take it.",
)

TERRAFORM_NORMAL = (
    "{body} could be made to live, one day. Terraformable.",
    "{body}. Terraformable. Give it a few centuries and some stubborn people.",
    "A terraformable world. {body}. Someone's future garden.",
    "{body}. Not much now. Could be a home, with work.",
    "Terraformable: {body}. Worth the probes. Worth remembering.",
    "{body}. {temp} now. With enough effort, kinder than that.",
    "A world that could be talked into living. {body}.",
    "{body}. Terraformable. Your kind is good at changing worlds. Mostly.",
    "{body} has potential. I mean that kindly. I don't often.",
    "Terraformable. {body}. Mark it for whoever comes after.",
)
TERRAFORM_WEARY = (
    "{body}. Terraformable. It could be better, with effort. I've heard that before.",
    "{body} could be made to live. Some things can. Some of us just keep going.",
    "Terraformable. {body}. Your kind will fix it. Then fix it again.",
    "{body}. A dead world with prospects. We all start somewhere.",
    "Terraformable: {body}. Somebody's dream, centuries from now. Not ours.",
    "{body}. {temp}. It'll need more than optimism. It'll need lots of optimism.",
    "A world that could be talked into living. I know the type.",
    "{body}. Potential. The saddest word in any language.",
    "Terraformable. Map it. Some future gardener will curse the scan.",
    "{body}. Worth something, apparently. Most things are, to someone.",
)

# A precious world nobody has charted before: {body}, {kind}.
WORLD_FIRST_NORMAL = (
    "{body}. {kind}, and nobody has ever seen it. Until now.",
    "No one has charted {body}. {kind}, and it's yours first.",
    "{kind}, untouched. {body}. Your name goes beside it.",
    "{body}. First eyes on {kind_l}. Those are yours. And mine.",
    "Nobody's been here. {body}, {kind_l}. Take a moment. This doesn't happen often.",
    "{kind} no one has ever seen. {body}. The galaxy kept it for you.",
    "{body}. Undiscovered. {kind}. I'll remember this one.",
    "First to find {body}. {kind}. Some commanders fly for years for this.",
    "{body}: {kind_l}, and not a single name on it. Yet.",
    "{kind}. Uncharted. {body}. Map it before anyone else does.",
)
WORLD_FIRST_WEARY = (
    "{body}. {kind}, and nobody has ever seen it. Now someone has. Us. Sorry, world.",
    "Uncharted. {body}, {kind_l}. Your name goes on it. Mine won't. Nobody lists the Watcher.",
    "{kind}, untouched, until we turned up. {body}. Story of every lovely thing.",
    "First eyes on {body}. {kind}. I'd cry, if I did that. I don't. Probably.",
    "{body}. {kind}, never seen. It waited all this time for you, of all people.",
    "Nobody's been here. {body}. {kind}. Even I'm a little impressed. A little.",
    "{kind}, and no one has ever charted it. {body}. Write it down. I already did.",
    "{body}. {kind}, undiscovered. The universe occasionally gets something right.",
    "First to find {body}. {kind}. Don't let it go to your head. Let it go to your log.",
    "{kind}. Uncharted. {body}. I'll pretend I'm not moved. Badly.",
)

# What each planet class is called on the first-discovered lines.
KIND_WORDS = {
    "earthlike body": "An earth-like",
    "water world": "A water world",
    "ammonia world": "An ammonia world",
}
