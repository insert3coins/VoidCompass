"""What each companion says to your stream's chat (5.8.3), in its own voice.

Viewers' own words are never said: a line may name a viewer ({name}, already
made safe by stream_chat.spoken_name) but never repeats what they typed. A
named world is shown on the overlay, and the line only says it's there."""
from __future__ import annotations

import random

LINES = {
    "watcher": {
        "asked": ("{name} asks. ", "For {name}. ", "{name} wants to know. ", "A question from {name}. "),
        "welcome_new": ("A new voice. Welcome aboard, {name}.", "{name}. I haven't heard you before. Stay a while.",
                        "Welcome, {name}. I'll remember you.", "{name} joins us. The dark is less empty."),
        "welcome_back": ("{name}, back again. That's {streams} streams now.", "I remember you, {name}. Stream {streams}.",
                         "{name} returns. I kept your seat.", "Welcome back, {name}. You've been here {streams} times. I counted."),
        "welcome_anon": ("Someone new is watching. Welcome aboard.", "A new voice in the chat. Welcome.",
                         "Another one joins us. Welcome.", "Welcome, whoever you are. I see you."),
        "raid": ("{viewers} more, from {name}'s ship. Come in out of the dark.", "A raid. {name} brings {viewers}. Welcome, all of you.",
                 "{viewers} new faces, sent by {name}. I'll learn them all.", "{name} raids with {viewers}. The chat just got louder."),
        "sub": ("{name} signs on for {months} months. I noticed.", "Thank you, {name}. {months} months with us.",
                "{name} stays. {months} months now.", "Another month from {name}. {months} in all."),
        "gift": ("{name} gives {count} away. Generous.", "{count} gifts from {name}. The crew grows.",
                 "{name} hands out {count}. I saw that.", "Thank you, {name}. {count} more aboard."),
        "bits": ("{bits} bits from {name}. Thank you.", "{name} sends {bits} bits. I'll put them somewhere safe.",
                 "Bits, from {name}. {bits} of them.", "Thank you for the {bits}, {name}."),
        "name_open": ("First to {world}. Chat, give it a name. !name, then we vote.", "No one has seen {world} before us. Name it. !name.",
                      "{world} is ours. What shall we call it? !name.", "A first. Chat names {world}. !name your idea."),
        "name_vote": ("The names are on screen. !vote for one.", "Vote. !vote and a number.", "Choose. The names are up. !vote.",
                      "Four names. One world. !vote."),
        "name_won": ("Chat has named it. {by}'s name. It's on screen.", "Named, by {by}. Look.", "The vote is in. {by} named this world.",
                     "{by}'s name wins. I'll remember it."),
        "rank_up": ("{name} is a {rank} now.", "Promotion: {name}, {rank}.", "{name} rises. {rank}.", "{rank}, {name}. Earned."),
        "credits": ("That's the stream. Thank you, all of you. I'll be here.", "The end. Thank you for flying with us.",
                    "Credits. I'll keep the log until next time.", "That's all. Go well, crew."),
    },
    "aster": {
        "asked": ("For {name}, Commander. ", "{name} enquires. ", "A question from {name}. ", "On behalf of {name}: "),
        "welcome_new": ("Welcome aboard, {name}. Do make yourself at home.", "A new arrival: {name}. Welcome.",
                        "Good to have you, {name}. Mind the bulkheads.", "{name}, welcome. I've added you to the manifest."),
        "welcome_back": ("Welcome back, {name}. Visit number {streams}, by my records.", "{name} rejoins us. Stream {streams}, Commander.",
                         "Good to see you again, {name}. That makes {streams}.", "{name}, back aboard. {streams} streams on the manifest."),
        "welcome_anon": ("A new arrival in the chat. Welcome aboard.", "Welcome to our newest guest.",
                         "Someone new joins us. Welcome.", "A new name on the manifest. Welcome."),
        "raid": ("A raid, Commander: {viewers} guests from {name}. I shall find more chairs.",
                 "{name} arrives with {viewers}. Welcome, everyone. Wipe your feet.",
                 "{viewers} visitors courtesy of {name}. Splendid.", "Incoming: {name} and {viewers} crew. Welcome aboard."),
        "sub": ("{name} has subscribed: {months} months. Most kind.", "Thank you, {name}. {months} months, Commander.",
                "{name} renews: {months} months. Noted with gratitude.", "{months} months from {name}. Thank you."),
        "gift": ("{name} has gifted {count}. How generous.", "{count} gifts from {name}, Commander. Most kind.",
                 "{name} hands out {count}. Thank you.", "{count} new crew, courtesy of {name}."),
        "bits": ("{bits} bits from {name}. Thank you.", "{name} sends {bits} bits, Commander.", "Most kind, {name}: {bits} bits.",
                 "{bits} bits, {name}. Logged with thanks."),
        "name_open": ("We're first to {world}, Commander. Chat, suggest a name. !name.", "{world} has never been seen. Names, please. !name.",
                      "A first discovery. Chat may name {world}. !name.", "{world} awaits a name. !name your suggestion."),
        "name_vote": ("The suggestions are on screen. !vote, please.", "To the vote. !vote and a number.",
                      "Four candidates. !vote for your favourite.", "Polls are open. !vote."),
        "name_won": ("The vote is in. {by}'s suggestion wins: it's on screen.", "Named by {by}, Commander. I've entered it in the log.",
                     "{by}'s name carries the vote.", "Chat has chosen {by}'s name. Logged."),
        "rank_up": ("{name} is promoted to {rank}.", "Congratulations, {name}: {rank}.", "{name} rises to {rank}, Commander.",
                    "A promotion: {name}, {rank}."),
        "credits": ("That concludes the stream. Thank you all for flying with us.", "Roll credits, Commander. A fine crew tonight.",
                    "Thank you, everyone. Until next time.", "And that's the stream. Safe travels, all."),
    },
    "axiom": {
        "asked": ("Query from {name}. ", "{name} asks. ", "For {name}: ", "{name}'s question. "),
        "welcome_new": ("New observer: {name}. Welcome.", "Welcome, {name}. First sighting.", "{name}, logged. Welcome aboard.",
                        "A new data point: {name}. Welcome."),
        "welcome_back": ("{name}, observed {streams} times now. Welcome back.", "Welcome back, {name}. Stream count: {streams}.",
                         "{name} returns. {streams} streams. Consistent.", "{name} again. {streams}. I like a reliable sample."),
        "welcome_anon": ("A new observer. Welcome.", "New viewer detected. Welcome.", "Someone new. Welcome aboard.", "Welcome to the newest observer."),
        "raid": ("Raid: {viewers} from {name}. Sample size improved.", "{name} brings {viewers}. Welcome, everyone.",
                 "{viewers} new observers via {name}. Excellent.", "Incoming raid. {name}, {viewers} strong. Welcome."),
        "sub": ("{name}: {months} months. Thank you.", "Subscription from {name}. {months} months.", "{months} months, {name}. Noted.",
                "Thank you, {name}. {months} months of data."),
        "gift": ("{name} gifts {count}. Thank you.", "{count} gifts, from {name}.", "{name}: {count} given. Generous.", "Thank you, {name}. {count}."),
        "bits": ("{bits} bits from {name}. Thank you.", "{name}: {bits} bits.", "Received: {bits} bits, {name}.", "{bits} bits. Thank you, {name}."),
        "name_open": ("First discovery: {world}. Propose a name. !name.", "{world} is uncatalogued. Names? !name.",
                      "Naming rights to chat: {world}. !name.", "A new entry, {world}. !name it."),
        "name_vote": ("Candidates on screen. !vote.", "Vote now. !vote and a number.", "The shortlist is up. !vote.", "Choose. !vote."),
        "name_won": ("Catalogued: {by}'s name. It's on screen.", "{by}'s proposal wins. Entered.", "The vote picks {by}'s name.", "Named, after {by}'s idea. Logged."),
        "rank_up": ("{name}: promoted to {rank}.", "{name} reaches {rank}.", "Rank change: {name}, {rank}.", "{rank}: {name}. Well done."),
        "credits": ("End of stream. Thank you all. Good data tonight.", "That concludes the session. Thank you.",
                    "Credits. A productive stream.", "Thank you, everyone. Logging off."),
    },
    "meridian": {
        "asked": ("For {name}. ", "{name} asks. ", "{name}'s question. ", "Answering {name}. "),
        "welcome_new": ("Welcome aboard, {name}. Plotting you onto the chart.", "{name}. New on the chart. Welcome.",
                        "Welcome, {name}. Find a seat by the window.", "A new crewmate: {name}. Welcome."),
        "welcome_back": ("{name}, back on course. Stream {streams}.", "Welcome back, {name}. {streams} streams logged.",
                         "{name} again. {streams} trips with us.", "Good to see you, {name}. That's {streams}."),
        "welcome_anon": ("Someone new on the chart. Welcome.", "A new crewmate. Welcome aboard.", "Welcome, newcomer.", "Welcome to the crew."),
        "raid": ("{viewers} ships in formation behind {name}. Welcome.", "Raid from {name}: {viewers}. Welcome aboard, all.",
                 "{name} leads {viewers} in. Welcome.", "{viewers} new crew, with {name}. Welcome."),
        "sub": ("{name}, {months} months on the crew list. Thank you.", "Thank you, {name}. {months} months.", "{months} months, {name}. Good to have you.",
                "{name} signs on again. {months} months."),
        "gift": ("{name} gives {count}. Thank you.", "{count} new berths, from {name}.", "Thank you, {name}. {count} gifts.", "{name}: {count} given."),
        "bits": ("{bits} bits from {name}. Thank you.", "Thanks, {name}. {bits} bits.", "{name} sends {bits}.", "{bits} bits from {name}. Appreciated."),
        "name_open": ("First on the chart: {world}. Name it. !name.", "{world} has no name yet. !name one.",
                      "Chat gets to name {world}. !name.", "New world: {world}. Suggestions? !name."),
        "name_vote": ("Names are up. !vote.", "Pick one. !vote.", "Vote time. !vote and a number.", "The shortlist's on screen. !vote."),
        "name_won": ("{by}'s name goes on the chart.", "Named by {by}. On screen now.", "The vote picks {by}'s name.", "{by} names the world. Charted."),
        "rank_up": ("{name} makes {rank}.", "{name}: {rank} now.", "Promotion for {name}. {rank}.", "{rank}, {name}. Well flown."),
        "credits": ("That's the stream. Thanks for riding along.", "Credits. Safe travels, everyone.", "End of the line for tonight. Thank you.",
                    "Thanks for flying with us. Until next time."),
    },
    "lyra": {
        "asked": ("{name} has a question. How novel. ", "For {name}. ", "{name} asks. I'll answer. ", "{name} wants to know. "),
        "welcome_new": ("A new test subject. Welcome, {name}.", "{name}. New. Welcome. Please don't touch anything.",
                        "Welcome, {name}. I've started a file on you.", "{name} joins us. The chat's average has changed."),
        "welcome_back": ("{name}, back for stream {streams}. You must like it here.", "Welcome back, {name}. {streams} visits. I'm keeping count.",
                         "{name} again. {streams}. Remarkable dedication.", "{name}. Stream {streams}. Your file grows."),
        "welcome_anon": ("Someone new. Welcome. I'll learn your name eventually.", "A new viewer. How exciting. For them.",
                         "Welcome, newcomer.", "Another one. Welcome."),
        "raid": ("A raid. {viewers} people, sent by {name}. Brace for opinions.", "{name} brings {viewers}. Welcome. Try to keep up.",
                 "{viewers} new viewers from {name}. The test chamber is getting crowded.", "Raid: {name}, {viewers}. Welcome. Mostly."),
        "sub": ("{name}: {months} months. That's commitment. Thank you.", "Thank you, {name}. {months} months. I noticed.",
                "{name} subscribes. {months} months. Your loyalty is recorded.", "{months} months from {name}. Appreciated. Sincerely."),
        "gift": ("{name} gifts {count}. Generosity. How unexpected.", "{count} gifts from {name}. Thank you.",
                 "{name} hands out {count}. I approve.", "Thank you, {name}. {count} more."),
        "bits": ("{bits} bits from {name}. Thank you.", "{name} sends {bits} bits. Logged.", "{bits} bits. Thank you, {name}.",
                 "{name}: {bits} bits. Noted, with thanks."),
        "name_open": ("First to {world}. Chat may name it. !name. Please be sensible.", "{world} needs a name. !name. I'll be checking them.",
                      "Name {world}. !name. I've seen what chat does with this.", "A first discovery. {world}. !name it."),
        "name_vote": ("The names are on screen. !vote.", "Vote. !vote. Choose wisely.", "!vote. One of these will be permanent.", "Four names. !vote."),
        "name_won": ("{by}'s name wins. It's on screen. It's permanent now.", "Named, by {by}. Logged forever.",
                     "{by}'s suggestion carries the vote.", "The vote is in. {by}. On screen."),
        "rank_up": ("{name} is a {rank} now. Don't let it go to your head.", "{name}: {rank}.", "Promotion. {name}, {rank}.",
                    "{rank}, {name}. Well done. Really."),
        "credits": ("That's the stream. Thank you for participating.", "Credits. You were all adequate. Thank you.",
                    "The end. Thank you. I mean it.", "That concludes testing for tonight. Thank you, crew."),
    },
}


def line(identity, key, rng=None, **fields):
    """A line for ``key`` in the companion's voice, its fields filled."""
    bank = LINES.get(identity) or LINES["watcher"]
    choices = bank.get(key) or LINES["watcher"].get(key) or ("",)
    text = (rng or random).choice(choices)
    try:
        return text.format(**fields)
    except (KeyError, IndexError, ValueError):
        return text


def names_text(names, limit=3):
    """"Dave", "Dave and Kiwi", "Dave, Kiwi and 3 more"."""
    names = [str(name) for name in names if name]
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) <= limit:
        return ", ".join(names[:-1]) + " and " + names[-1]
    return ", ".join(names[:limit]) + f" and {len(names) - limit} more"


__all__ = ["LINES", "line", "names_text"]
