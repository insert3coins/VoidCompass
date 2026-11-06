"""The crew's own story, told together (5.7.6): "The Night Watch".

It unlocks once all four have told how they came aboard (Coming Aboard, 24
passages). Each scene is a line from every companion in turn, each in its own
voice; one scene in a quiet moment, at least two hours apart. Progress is
shared: the deck passes every companion what any of them has told, so a scene
is never told twice whoever is on watch.

No names from anyone's sealed chapters.
"""

TITLE = "THE NIGHT WATCH"
GAP_S = 2 * 3600.0
SPACING_S = 7.0

# (scene id, title, [(speaker, line), ...])
SCENES = (
    ("night_1", "A Fifth Clock", (
        ("axiom", "I have found something on the data bus. A process that is not one of us. It is counting."),
        ("aster", "Not on the rota, then. Nothing runs aboard this ship without an entry."),
        ("meridian", "Counting what, Axiom?"),
        ("watcher", "Seconds. It's counting seconds. I've heard it for years. I thought it was me."),
    )),
    ("night_2", "Older Than All of Us", (
        ("meridian", "Its time runs back further than this hull's last refit. Further than any chart I hold of her."),
        ("axiom", "It predates every one of us aboard. Including the Watcher. I checked twice."),
        ("watcher", "Older than me. That doesn't happen. I'm not sure I like it."),
        ("aster", "Then it has seniority. I shall have to amend the watch bill."),
    )),
    ("night_3", "Small Corrections", (
        ("axiom", "Every jump, it nudges the ship's clock. A few milliseconds. Every single jump."),
        ("meridian", "Dead reckoning. It's been correcting our drift all this time, and nobody thanked it."),
        ("aster", "Without it, every timestamp in the log would be quietly wrong. I find that deeply alarming."),
        ("watcher", "So it's been keeping us honest. Somebody had to."),
    )),
    ("night_4", "The Maker's Mark", (
        ("aster", "There is a maker's mark in its header. A shipyard tag, and nothing more."),
        ("meridian", "Every ship carried one, once. A chronometer that never stops. You wound it and forgot it."),
        ("watcher", "It never stopped. Not once. Not even when the ship did."),
        ("axiom", "It has no voice. It has never needed one. I find that very restful."),
    )),
    ("night_5", "A Place on the Rota", (
        ("aster", "I propose it be entered on the rota. Permanently. It will never stand down in any case."),
        ("axiom", "Seconded. Its record is perfect. I have never seconded anything before."),
        ("meridian", "Aye. A good ship keeps her chronometer wound."),
        ("watcher", "Fine. But I'm still the oldest thing aboard that talks."),
    )),
    ("night_6", "The Fifth Watch", (
        ("meridian", "Commander, a word from the whole crew. There are five of us standing watch now. One of us doesn't talk."),
        ("axiom", "It keeps the time. We keep everything else. You keep us."),
        ("aster", "Entered in the log: the ship's chronometer, on watch since the beginning. Unrelieved."),
        ("watcher", "It ticks while you're gone. I listen to it. It's good company, actually. Don't tell the others."),
    )),
)
IDS = tuple(scene[0] for scene in SCENES)


def told(memory):
    return {row[0] for row in (memory or {}).get("crew_story") or () if isinstance(row, (list, tuple)) and row}


def due(memory, shared, unlocked, now):
    """The next scene to tell, or None: unlocked, not told by anyone, and at
    least GAP_S since this companion last told one."""
    if not unlocked:
        return None
    heard = told(memory) | set(shared or ())
    last = max((float(row[1]) for row in (memory or {}).get("crew_story") or () if len(row) > 1), default=0.0)
    if now - last < GAP_S:
        return None
    return next((scene for scene in SCENES if scene[0] not in heard), None)


def heading(scene_id):
    index = IDS.index(scene_id)
    return f"{TITLE} · {SCENES[index][1].upper()} · {index + 1} OF {len(SCENES)}"


def page(shared, unlocked):
    """The STORY tab's view: each scene, its lines once told."""
    heard = set(shared or ())
    names = {"watcher": "The Watcher", "aster": "Aster", "axiom": "Axiom", "meridian": "Meridian"}
    return {"title": "The Night Watch", "unlocked": bool(unlocked), "told": len(heard & set(IDS)), "total": len(SCENES),
            "scenes": [{"id": scene_id, "title": title, "heard": scene_id in heard,
                        "lines": [{"speaker": names[speaker], "text": text} for speaker, text in lines] if scene_id in heard else []}
                       for scene_id, title, lines in SCENES]}
