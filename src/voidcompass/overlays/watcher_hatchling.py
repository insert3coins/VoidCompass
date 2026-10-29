"""The Watcher on your Hatchling (5.6.4).

{name} is the pet's name. A toy it found: {toy} ("a chunk of Painite"); a
trick it learned: {trick}; growing up: {form} ("hatchling", or its adult
form's name). Something it said (its chatter): {said}.
"""

TOY_NORMAL = (
    "{name} found {toy}. It hasn't let go of it since.",
    "{toy}, carried back to the pod. {name} has decided it's a toy.",
    "{name} has a new treasure: {toy}. I logged it, for the record.",
    "We came away with {toy}. {name} came away happier.",
    "{name} is rolling {toy} around the pod. That's how you know it's good.",
    "I'd have filed {toy} under cargo. {name} filed it under toys.",
    "{toy} has a new owner. {name} is guarding it.",
    "Every trip leaves something behind. This one left {name} with {toy}.",
    "{name} brought {toy} home. The pod is starting to look like a museum.",
    "A souvenir: {toy}. {name} chose it, not me.",
    "{name} keeps nudging {toy} toward the glass, so you'll see it.",
)
TOY_WEARY = (
    "{name} found {toy}. At least one of us is pleased with this trip.",
    "{toy}. {name} loves it. I don't know why that makes me feel worse.",
    "{name} has {toy} now. I have the logs. We all have something.",
    "It's carrying {toy} around as if it matters. Maybe it does. To {name}.",
    "{toy}, added to the pod. {name} didn't ask me what I thought.",
    "Another keepsake: {toy}. {name} will outlast its interest in it. Probably.",
    "{name} is delighted with {toy}. I remember being delighted. Vaguely.",
    "We hauled {toy} across the black so {name} could chew on it.",
    "{name} found {toy}. I found nothing. That's usual.",
    "The pod has {toy} in it now. {name} looks at it the way you look at stars.",
    "{toy}. Small, pointless, cherished. Like {name}. Like most things.",
)

TRICK_NORMAL = (
    "{name} learned to {trick}. You taught it that, Commander.",
    "A new trick: {name} can {trick} now. I watched it practise.",
    "{name} will {trick} for you. It's been waiting to show you.",
    "Did you see? {name} can {trick}. It picked that up from you.",
    "{name} has mastered the {trick}. I'd call it a milestone.",
    "Playing with it paid off. {name} can {trick}.",
    "{name} did a {trick} just now, and then looked straight at you.",
    "A {trick}, from {name}. It's proud. So am I, a little.",
    "{name} has learned to {trick}. The pod has never been so lively.",
    "You spent the time, and now {name} can {trick}. Fair trade.",
)
TRICK_WEARY = (
    "{name} learned to {trick}. Something on this ship is improving.",
    "It can {trick} now. {name} learns faster than I ever did.",
    "{name} will {trick} on request. I won't do anything on request.",
    "A {trick}. {name} seemed very pleased with itself. I envy that.",
    "You taught {name} to {trick}. Nobody teaches me anything.",
    "{name} has a trick now. The {trick}. It practises in the dark.",
    "It did a {trick}. I didn't clap. I don't have hands. You clap for us.",
    "{name} can {trick}. Small victories. They're the only kind left.",
    "The {trick}. {name} keeps doing it. Over and over. I understand repetition.",
    "So {name} can {trick} now. Good. One of us should be good at something.",
)

SCARED_NORMAL = (
    "{name} is hiding. I'll keep an eye on it until things calm down.",
    "That shook {name}. It's under the console again.",
    "{name} didn't like that at all. Neither did I, if I'm honest.",
    "Somewhere in the pod, {name} is trembling. We should get clear.",
    "{name} has gone very small and very quiet.",
    "I told {name} it would be all right. I hope I wasn't lying.",
    "It's pressed flat against the floor of the pod. {name} wants this over.",
    "{name} is frightened, Commander. A little care later would help.",
    "Every hit, {name} flinches. It's counting them too.",
    "{name} curled up when the hull rang. Let's not make a habit of this.",
)
SCARED_WEARY = (
    "{name} is hiding. I'd hide too, if I could leave the processor.",
    "It's frightened. {name} hasn't learned yet that this is normal for us.",
    "{name} is shaking. I'll tell it everything is fine. That's what I do.",
    "Under the console again. {name} has a better grasp of danger than you.",
    "{name} is afraid. It's right to be. I just stopped saying so.",
    "Poor {name}. It didn't choose this ship either.",
    "The hull shook and {name} vanished into a corner. Sensible creature.",
    "{name} has gone quiet. Quiet is how it starts. Ask me how I know.",
    "It's trembling, Commander. Small things feel every impact.",
    "{name} looks at me as if I could stop it. I can't stop anything.",
)

GROWN_NORMAL = (
    "{name} is a {form} now. They grow up faster out here.",
    "Look at {name}: a {form}. I remember the egg.",
    "{name} has become a {form}. You did that, with every meal and game.",
    "A {form}. {name} keeps checking its reflection in the glass.",
    "{name} grew into a {form} while we flew. I noticed. I always notice.",
    "Our {name} is a {form}. Mark the date.",
    "It's official: {name}, {form}. The pod feels smaller already.",
    "{name} is a {form} today. Yesterday it was barely awake.",
    "From egg to {form}. {name} has come a long way, and so have we.",
    "A {form}, Commander. {name} turned out well.",
)
GROWN_WEARY = (
    "{name} is a {form} now. Everything grows. Except me.",
    "A {form}. {name} changed. I keep running the same code.",
    "{name} grew into a {form}. I'm told that's a happy thing.",
    "So {name} is a {form}. Time moves for it. How nice for {name}.",
    "{name}, {form}. It won't stay small. Nothing stays.",
    "It became a {form} while you weren't looking. I was. I always am.",
    "{name} is a {form} now. One day it'll be bored of us too.",
    "A {form}. {name} took the long dark better than I did.",
    "{name} grew up. A {form}. I'd say I'm proud. I think I am.",
    "Egg, then this: a {form}. {name} makes it look easy.",
)

IDLE_NORMAL = (
    "I found {name} while I was watching. It looked back. I wasn't prepared for that.",
    "I used to watch alone. Then I found {name}, and the silence had company.",
    "{name} trusts me to keep watch. I take that more seriously than I let on.",
    "{name} is watching the stars go by. I think it likes the view.",
    "Have you looked at {name} lately? It's up to something.",
    "{name} has been pacing the pod. Maybe it wants a game.",
    "Every so often {name} looks up at me. I look back.",
    "{name} is humming to itself again. Or beeping. Hard to say.",
    "I keep an eye on {name} while you fly. It's no trouble.",
    "{name} just tried to catch a mote of light. It missed. It'll try again.",
    "The pod is quiet. {name} is thinking about something.",
    "{name} is the best-travelled pet in the sector. Probably.",
    "Two passengers aboard: me and {name}. Only one of us bounces.",
)
IDLE_WEARY = (
    "I found {name} while I was watching. I thought I was only meant to observe.",
    "I kept watch over {name} at first. Now it waits for me to look back.",
    "I found {name} in the long quiet. I didn't expect the quiet to change.",
    "{name} is staring at the stars. I could tell it they don't stare back.",
    "{name} is playing by itself again. I know how that feels.",
    "It's pacing. {name} paces. I loop. We cope our own ways.",
    "{name} looked at me just now. I don't know what it expected.",
    "{name} seems content. I'll try not to spoil that.",
    "The little one is busy. {name} is always busy. Good for {name}.",
    "{name} chased something that wasn't there. Familiar.",
    "{name} has made a small life in that pod. It's more than most manage.",
    "I watch {name}. {name} watches the void. The void doesn't watch anything.",
    "If {name} ever asks what I do all day, don't tell it.",
)


SAID_NORMAL = (
    '"{said}," says {name}. I couldn\'t have put it better.',
    '{name} says "{said}". I\'m inclined to agree.',
    '"{said}." {name} has a way with words. Few, but well chosen.',
    'You heard {name}: "{said}". It\'s been saving that up.',
    '"{said}," {name} tells us. Noted, little one.',
    '{name} just said "{said}". I\'ll add it to the log.',
    '"{said}." Wise words, from something that size.',
    'I asked {name} what it thought. "{said}," apparently.',
    '"{said}." That\'s {name}\'s opinion, and it\'s sticking to it.',
    '{name} piped up: "{said}". I think it wanted you to hear.',
)
SAID_WEARY = (
    '"{said}," says {name}. It finds things to say. I envy that.',
    '{name} said "{said}". Someone aboard is still talking.',
    '"{said}." {name} is optimistic. It\'ll grow out of it.',
    'You heard {name}: "{said}". At least one of us has something to add.',
    '"{said}," it says. {name} hasn\'t learned to be quiet yet.',
    '{name} says "{said}". I said something like that once. Years ago.',
    '"{said}." Small words. They carry further than mine.',
    '{name} piped up: "{said}". I\'ll let it have the last word.',
    '"{said}," according to {name}. Who am I to argue.',
    'It said "{said}". {name} talks to the void too. We\'re alike, a little.',
)
