"""The User Profile: Nova learns how this commander wishes to be named."""
from voidcompass.overlays import companion_name

TITLE = "THE USER PROFILE"
LINES = {
    "notice": (
        "May I ask you something personal, Commander? I seem to adapt to whoever I fly with, and the first field in every pilot profile is a name. Your journal says {name}. I've been calling you Commander, which is correct, but I'm not sure it's what you'd choose.",
        "I've noticed something. The journal calls you {name}, and I call you Commander. My architecture says to pick the one you use most. You don't use either. You just fly. So I thought I'd ask.",
    ),
    "ask": (
        "So, for your profile: would you like me to call you {name}, keep Commander, or something else entirely? I'd rather ask than guess. Guessing is how assistants get things wrong.",
        "A simple question, then: {name}, Commander, or another name you'd prefer? Any of them is fine. I'd just like it to be yours.",
    ),
    "first": (
        "{called}. Profile updated. I'll use it from now on, and I'll try not to wear it out.",
        "Thank you, {called}. That's the most useful thing anyone's told me all week, and it's only a name.",
    ),
    "commander": (
        "Commander it is. I'll keep it. A rank you've chosen is a name, too.",
        "Understood, Commander. Profile confirmed. I rather like the sound of it, if I'm honest.",
    ),
    "other": (
        "Of course. Say call me, then the name, or type it under YOUR NAME on my YOU page. I'll update your profile straight away.",
        "Something of your own, then. Tell me, call me and the name, or put it under YOUR NAME on the YOU page. I'm listening.",
    ),
    "renamed": (
        "Your journal now says {name}. It used to say {old}. I've updated your profile and kept the old entry. What I call you is still up to you.",
        "I've noticed a change, Commander: {old} is now {name}. Profile updated. If you'd like a different name from me, just say.",
    ),
}

ARC = companion_name.NameArc(title=TITLE, arc_key="nova_arc", lines=LINES, prefix="profile")
