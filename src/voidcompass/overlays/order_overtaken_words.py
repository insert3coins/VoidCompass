"""Overtaken (5.7.7): someone else got to a first before you. The journal
says so (a Scan with the body already mapped); the officer takes it with
grace and, where there's another target, offers it. Fields: {title}, {body}."""

OVERTAKEN = {
    "watcher": {
        "normal": {
            "overtaken": ("Someone mapped {body} before us. That's how it goes.", "{body}'s been mapped. Not by us. Let it go.",
                          "Someone else got there first. {title} is gone.", "Beaten to {body}. There'll be others.",
                          "{title}. Someone was quicker. It doesn't matter as much as it feels."),
        },
        "weary": {
            "overtaken": ("Someone mapped {body} before us. Of course they did.", "{body}, already mapped. By a stranger. Naturally.",
                          "Beaten again. {title} is someone else's now.", "{body}. Taken. I'm not surprised. I'm never surprised.",
                          "Someone got there first. They always do. {title}'s gone."),
        },
    },
    "aster": {
        "plain": {
            "overtaken": ("Overtaken: {body} already mapped.", "{title}: overtaken. No penalty.", "First map of {body} taken by another.",
                          "Order closed: overtaken."),
        },
        "voiced": {
            "overtaken": ("Commander, another commander has mapped {body} before us. I've closed {title} without penalty.",
                          "We've been overtaken on {body}. Graciously noted in the register.",
                          "{body} carries someone else's first map now. A pity. The register moves on.",
                          "Overtaken, I'm afraid. {title} is closed; no fault recorded.",
                          "Someone beat us to {body}. I shall look for another entry."),
        },
    },
    "axiom": {
        "plain": {
            "overtaken": ("{body}: already mapped by another commander.", "Overtaken. {title} closed.", "First map lost: {body}.",
                          "Target taken. Order closed."),
        },
        "voiced": {
            "overtaken": ("{body} was mapped by someone else before us. The data still exists; it just isn't ours.",
                          "Overtaken on {body}. I'm recalculating. There are other worlds.",
                          "Someone else's probes reached {body} first. I find that irritating. Briefly.",
                          "The scan says {body} is already mapped. {title} is closed; I'll find another.",
                          "We were second. {title} is closed. Second is still data; just less satisfying."),
        },
    },
    "meridian": {
        "plain": {
            "overtaken": ("Overtaken on {body}.", "{title}: another ship got there first.", "{body} already mapped. Order struck.",
                          "Beaten to it. Closed."),
        },
        "voiced": {
            "overtaken": ("Another ship got to {body} first, Commander. It happens to the best of us.",
                          "We've been overtaken on {body}. No shame in it; the sea's crowded these days.",
                          "{body}'s been mapped by someone else. I'll chart another course.",
                          "Beaten by a faster hull, Commander. {title} is struck. Fair winds to them.",
                          "{title} is struck: someone mapped {body} before we could."),
        },
    },
    "lyra": {
        "plain": {
            "overtaken": ("Overtaken: {body} already mapped.", "{title}: target taken.", "{body} mapped by another commander.",
                          "Order closed. Someone else got there first."),
        },
        "voiced": {
            "overtaken": ("Oh. Someone mapped {body} before us. Rude, but fair.",
                          "{body}'s already mapped. Another commander beat us to it. Next one's ours.",
                          "We were overtaken on {body}. I'll find us a fresher target.",
                          "Somebody got to {body} first. I'm not sulking. I'm recalibrating.",
                          "{title}: overtaken. Fuel's still good for the next one."),
        },
    },
}
