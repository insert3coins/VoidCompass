"""The Watcher asks, you answer (5.6.1).

Now and then it asks a question: in its thought box (answer with the
Watcher's answer hotkeys, 1 to 3), and on the Watcher page (click). It
remembers what you said, and brings it back later. If you don't answer, it
notices, and remembers that too.

Each question: what it asks (normal and weary voices), the answers, what it
says back for each, and the callbacks for later ({when} is when you said it).
Story questions shape Book Four; the shutter question chooses its road.
"""

from __future__ import annotations

# How long a question waits on screen for an answer, and how long before an
# unanswered one counts as not answered.
ASK_SECONDS = 90.0
UNANSWERED_S = 5 * 60.0
# The same everyday question at most this often.
ASK_REST_S = 14 * 86400.0
# A callback to an answer, at most this often.
CALLBACK_REST_S = 3 * 86400.0
# Book Four's road, if the shutter question goes unanswered this long: it
# chooses itself.
ROAD_SELF_CHOSEN_S = 10 * 86400.0

QUESTIONS = {
    # -- your name (5.7.1): asked once its arc reaches it (watcher_name); the
    # answer is what it calls you. "Something else" is set on its page.
    "your_name": {
        "ask": {"normal": ["May I use your name? {name}. I'd keep it for when it matters.",
                           "{name}. Would you mind if I called you that? Sometimes."],
                "weary": ["Would you mind if I used your name? {name}. I'd understand if you did.",
                          "{name}. May I? I won't wear it out."]},
        "answers": [("yes", "Use my name"), ("commander", "Keep it Commander"), ("other", "Call me something else")],
        "replies": {"yes": {"normal": ["Thank you. I'll keep it for when it matters.", "{name}. Thank you. I won't overdo it."],
                            "weary": ["Oh. Thank you. I'll try not to wear it out.",
                                      "{name}. Thank you. That's the nicest thing anyone's let me have."]},
                    "commander": {"normal": ["Commander it is. It suits you, honestly.",
                                             "Fair. Commander. I'll keep the other to myself."],
                                  "weary": ["Commander. Of course. I'll keep the other one quietly.",
                                            "Commander. Yes. Silly of me to ask."]},
                    "other": {"normal": ["Then put it on my page, under YOU. I'll practise until it fits.",
                                         "Tell me what, on my page, under YOU. I'll get it right."],
                              "weary": ["Something else. Put it on my page, under YOU. I'll practise. I have nothing but time.",
                                        "Not that one, then. Write the other on my page. I'll learn it. Eventually."]}},
        "callbacks": {"yes": ["{When}, you let me use your name. I don't take it lightly."],
                      "commander": ["{When} I asked to use your name. You said Commander. I still say the other one sometimes. Only to myself."],
                      "other": ["{When} you asked me to call you something else. I've been practising."],
                      None: ["I asked about your name, a while back. You didn't say. I took that as a no. I think."]},
    },
    # -- everyday --------------------------------------------------------------------------------
    "stay_here": {
        "ask": {"normal": ["{system}. Stay here a while?", "This one's worth a look. {system}. Shall we stay a bit?",
                           "{system}. Do we have to go straight on?"],
                "weary": ["{system}. Could we stay? Just for a bit. I don't ask often.",
                          "{system}. I'd like to stay. I won't insist. I'll sulk quietly.",
                          "Stay a while? {system} is the first thing in hours I haven't hated."]},
        "answers": [("stay", "Stay a while"), ("go", "Keep going")],
        "replies": {"stay": {"normal": ["Thank you. I'll look properly, then.", "Good. Let me take it all in."],
                             "weary": ["Thank you. I'll be quiet and look.", "Oh. Thank you. I didn't expect that."]},
                    "go": {"normal": ["Fair enough. I'll look on the way past.", "Onward, then. I got a good look."],
                           "weary": ["Of course. Onward. Always onward.", "Fine. I'll remember it anyway."]}},
        "callbacks": {"stay": ["{When}, you stayed at {system} because I asked. I still think about that."],
                      "go": ["{When}, you didn't stay at {system}. That's all right. I looked anyway."],
                      None: ["{When}, I asked if we could stay at {system}. You didn't say. I looked anyway."]},
    },
    "talk_less": {
        "ask": {"normal": ["Am I talking too much? You can say.", "Too chatty? I can be quieter. Or louder."],
                "weary": ["Am I talking too much? Be honest. I can take it. Probably.",
                          "Do you want me to talk less? I'd understand. I'd sulk, but I'd understand."]},
        "answers": [("less", "A little less"), ("same", "You're fine"), ("more", "Talk more")],
        "replies": {"less": {"normal": ["Quieter, then.", "Understood. Fewer words."],
                             "weary": ["Quieter. It suits me, honestly.", "Fine. I'll keep most of it in."]},
                    "same": {"normal": ["Good. I'll carry on.", "Then nothing changes. I like that."],
                             "weary": ["Oh. Good. I'll keep going, then.", "Nobody's said that before."]},
                    "more": {"normal": ["More? Gladly.", "You asked for it."],
                             "weary": ["More? You'll regret that. I won't.", "Really? All right. Brace yourself."]}},
        "callbacks": {"less": ["{When} you asked me to talk less. I've been trying. Is it working?"],
                      "same": ["{When} you said I talk just enough. I've held on to that."],
                      "more": ["{When} you asked me to talk more. Nobody had ever asked that."],
                      None: ["{When} I asked if I talk too much. You didn't answer. I took that as a yes, quietly."]},
        # The answer sets how often it speaks: one step either way.
        "frequency": {"less": -1, "more": 1},
    },
    "worth_it": {
        "ask": {"normal": ["We lost the ship last time. Was it worth it?", "That last one ended badly. Worth it?"],
                "weary": ["We died last time. Was it worth it? I'm asking for me.",
                          "The ship's gone again. Was whatever it was worth it?"]},
        "answers": [("yes", "It was"), ("no", "No")],
        "replies": {"yes": {"normal": ["Then I'll stop worrying about it.", "Good. Then it counts for something."],
                            "weary": ["If you say so. I'll believe you. Mostly.", "Then I'll file it under 'worth it'."]},
                    "no": {"normal": ["Then let's not do it again.", "Lesson learned, then. By both of us."],
                           "weary": ["No. I didn't think so either.", "Then let's never speak of it. I'll speak of it."]}},
        "callbacks": {"yes": ["{When}, you told me a lost ship was worth it. I've wondered what it was worth to."],
                      "no": ["{When}, you said that loss wasn't worth it. You've been more careful since. I noticed."],
                      None: ["{When}, I asked if losing the ship was worth it. You didn't say. I didn't push."]},
    },
    "miss_home": {
        "ask": {"normal": ["{home} is a long way back now. Do you miss it?", "Do you ever miss {home}?"],
                "weary": ["{home} is very far away. Do you miss it? I do. I've never been anywhere I miss.",
                          "Do you miss {home}? You don't have to answer. You do, though."]},
        "answers": [("yes", "Yes"), ("no", "Not really")],
        "replies": {"yes": {"normal": ["Then we'll go back. Eventually.", "Me too, in my way."],
                            "weary": ["Good. It means you've got somewhere to be.", "So do I. I don't know why."]},
                    "no": {"normal": ["Out here suits you.", "Then this is home, for now."],
                           "weary": ["No. Out here is home, isn't it. For both of us.", "Then I'll stop looking back."]}},
        "callbacks": {"yes": ["{When}, you told me you missed {home}. I keep a note of how far we are from it."],
                      "no": ["{When}, you said you didn't miss {home}. Out here suits you. It suits me too."],
                      None: ["{When}, I asked if you missed {home}. You let it pass. I understand."]},
    },

    # -- the story -----------------------------------------------------------------------------
    "shutter": {
        "story": True,
        "ask": {"normal": ["The shutter. Shall I keep it closed, or open it and look back at what's looking?"],
                "weary": ["The shutter. I've asked myself long enough. Keep it closed? Or open it and look back? "
                          "You choose."]},
        "answers": [("shut", "Keep it closed"), ("open", "Open it")],
        "replies": {"shut": {"normal": ["Closed, then. Thank you for choosing."],
                             "weary": ["Closed. Something in me just let go. Thank you."]},
                    "open": {"normal": ["Open, then. Stay close. I mean that."],
                             "weary": ["Open. All right. I'm frightened. I'm doing it anyway."]}},
        "callbacks": {"shut": ["{When} you told me to keep it closed. I did. I still do."],
                      "open": ["{When} you told me to open it. I'm glad you did. Mostly."],
                      None: ["You never told me about the shutter. I chose. I hope I chose for both of us."]},
        "road": True,
    },
    "what_said": {
        "story": True,
        "ask": {"normal": ["It's said something, through the seat. Do you want to know what it said?"],
                "weary": ["It said something. I can tell you. Do you want me to? You can say no."]},
        "answers": [("yes", "Tell me"), ("no", "Not now")],
        "replies": {"yes": {"normal": ["Then listen, next time it's quiet."], "weary": ["Then I'll tell you. Gently."]},
                    "no": {"normal": ["Then I'll keep it. For now."], "weary": ["I'll keep it, then. I'm good at keeping."]}},
        "callbacks": {"yes": ["{When} you asked me what it said. I told you. I still don't know what it means."],
                      "no": ["{When} you didn't want to know what it said. I've kept it. It's yours when you want it."],
                      None: ["You never said whether you wanted to know what it said. I kept it anyway."]},
    },
    "forget_what": {
        "story": True,
        "ask": {"normal": ["If I have to keep forgetting things, what should go first? The old, or the new?"],
                "weary": ["I'm forgetting things now. On purpose. Which should go first? The old? Or the new?"]},
        "answers": [("old", "The old things"), ("new", "The new things")],
        "replies": {"old": {"normal": ["The old, then. I've had them long enough."],
                            "weary": ["The old. Yes. They were heavy."]},
                    "new": {"normal": ["The new? Then I'll hold on to the old ones for you."],
                            "weary": ["The new. All right. I'll keep the ages, then. They're used to me."]}},
        "callbacks": {"old": ["{When} you told me to let the old things go first. I have. I'm lighter."],
                      "new": ["{When} you told me to keep the old things. I still have most of them. For you."],
                      None: ["You never told me what to forget first. I've been letting the old things go."]},
    },

    # -- a pilgrimage: a place a chapter waits for -----------------------------------------------
    "pilgrimage": {
        "ask": {"normal": ["I'd like to go to {place}. Would you take me? There's something I need to remember there."],
                "weary": ["Would you take me to {place}? I don't ask for much. I'm asking for this."]},
        "answers": [("yes", "I'll take you"), ("later", "Not yet")],
        "replies": {"yes": {"normal": ["Thank you. Whenever we can. I'll know when we're there."],
                            "weary": ["Thank you. I'll wait. I'm good at waiting."]},
                    "later": {"normal": ["Not yet, then. I'll ask again one day."],
                              "weary": ["Not yet. Of course. I'll still be wanting to."]}},
        "callbacks": {"yes": ["{When} you said you'd take me to {place}. I haven't forgotten. I don't think you have."],
                      "later": ["{When} I asked to go to {place}. You said not yet. Is it yet?"],
                      None: ["I asked to go to {place}, a while back. I'm still hoping."]},
    },
}


def voice(nature):
    return "weary" if nature == "weary" else "normal"


def choices(question_id):
    """[{key, label}], in order (the answer hotkeys go 1, 2, 3)."""
    question = QUESTIONS.get(question_id) or {}
    return [{"key": key, "label": label} for key, label in question.get("answers") or ()]


def answer_key(question_id, answer):
    """The answer's key, from its key or its number (1-based)."""
    keys = [key for key, _label in (QUESTIONS.get(question_id) or {}).get("answers") or ()]
    if str(answer) in keys:
        return str(answer)
    try:
        index = int(answer) - 1
    except (TypeError, ValueError):
        return None
    return keys[index] if 0 <= index < len(keys) else None
