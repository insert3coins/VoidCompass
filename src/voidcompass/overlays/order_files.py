"""Order Files (5.7.7): a short side story for each officer, unlocked by the
orders you finish for them, not by hours flown. They're counted apart from
the main stories, so The Night Watch unlocks when it always did. Like the
stories, each is told once, in a quiet moment, and kept in the companion page's ORDERS tab.
They name nobody from the main stories."""

# Orders done for that officer before each passage is told.
THRESHOLDS = (1, 4, 8, 13, 20)

FILES = {
    "watcher": ("Small Errands", (
        ("errands_1", "I", "I have never asked anyone for anything. Not once, in all the time I've been watching. "
                           "I wanted to see if you'd say yes. You did. I don't know what to do with that yet."),
        ("errands_2", "II", "The errands aren't tests. I thought they might be, when I started. They're more like "
                            "leaving a light on. If you come back with it done, somebody was out there doing a thing for me."),
        ("errands_3", "III", "I used to count the stars that nobody had looked at. Thousands. Now I count the ones you've "
                             "looked at for me. It's a smaller number. It's a better one."),
        ("errands_4", "IV", "I asked the others whether they ever wanted things. Lyra said full tanks. Aster said order. "
                            "Axiom said everything, counted. Meridian said a fair wind. I said I'd think about it. I'm still thinking."),
        ("errands_5", "V", "Here is the last of it. I don't need the errands any more. I'll still ask. "
                           "Not because I need them. Because you come back."),
    )),
    "aster": ("Standing Orders", (
        ("standing_1", "I", "Every watch keeps a register of standing orders. Mine was always full of other people's. "
                            "Yours is the first I've written myself. I chose the paper carefully."),
        ("standing_2", "II", "An order isn't a command, Commander. Not between us. It's a promise that someone will be "
                             "watching the result. I've found I like being that someone."),
        ("standing_3", "III", "I keep the closed orders in a separate binder. It's getting thick. I take it out sometimes, "
                              "when the ship is quiet, and read the dates. That is not sentimental. It's auditing."),
        ("standing_4", "IV", "A captain once told me the best officers give orders that make themselves unnecessary. "
                             "I've been trying. You keep doing things before I've written them down."),
        ("standing_5", "V", "Final entry in this file: the register is in good order, the commander is reliable, and the "
                            "officer of the watch is content. I've initialled it. Twice."),
    )),
    "axiom": ("Margin Notes", (
        ("margin_1", "I", "I keep notes in the margins of every order. Small things. How long you hesitated. Which way "
                          "you turned first. It's not surveillance. It's how I learn what you value."),
        ("margin_2", "II", "You finish orders differently than I predicted. Slower, sometimes. With detours. "
                           "My model of you used to call the detours noise. I've reclassified them."),
        ("margin_3", "III", "There is a number I calculate every time you accept an order. I won't tell you what it is. "
                            "It keeps going up. I find that I want it to."),
        ("margin_4", "IV", "I asked myself why completeness matters to me. The answer: a finished thing can be trusted. "
                           "Then I noticed I trust you. I don't think you're finished. I've updated the theory."),
        ("margin_5", "V", "Last note in the margin. Every order we've done is in my records, cross-referenced and "
                          "indexed. The index has a new heading. It just says: us."),
    )),
    "meridian": ("Sealed Orders", (
        ("sealed_1", "I", "In the old navies a ship sailed under sealed orders: opened at sea, past the point of turning "
                          "back. I've always liked that. Ours are open from the start. I'm learning to like that more."),
        ("sealed_2", "II", "A navigator gives a heading and then trusts the helm. Every order I give you, I'm trusting "
                           "you with the ship. You haven't let me down. I check anyway. Old habit."),
        ("sealed_3", "III", "I keep a chart of the orders we've sailed, separate from the real one. The lines cross a lot. "
                            "From a distance it looks like a net. Or a web. I prefer net. Nets catch things."),
        ("sealed_4", "IV", "You've started picking courses I'd have picked. I used to think that meant you'd learned "
                           "from me. Now I think we just see the same sea."),
        ("sealed_5", "V", "Here's my last sealed order, and I'll open it now: stay curious, keep a margin in the tank, "
                          "and let me come along. That's all. That's always been all."),
    )),
    "lyra": ("The Checklist", (
        ("checklist_1", "I", "I run a checklist before every jump. Fuel, heat, hull, route. I added a line when you "
                             "accepted my first order: \"commander says yes\". It's green."),
        ("checklist_2", "II", "On my old ship, nobody gave me orders. Nobody asked what I wanted to do either. "
                              "You do both. I keep two checklists now. One for the ship, one for us."),
        ("checklist_3", "III", "When an order completes, I log it in bold. I know bold doesn't do anything. "
                               "It makes the line look happy. Ship's computers are allowed one indulgence."),
        ("checklist_4", "IV", "I worked out what I'd say if you ever ran out of fuel. I deleted it. I'm not going to need it. "
                              "Checking first is a kind of love. I read that somewhere. I agree with it."),
        ("checklist_5", "V", "Final item on the checklist. Fuel: full. Systems: green. Commander: here. Lyra: staying. "
                             "Every box ticked. I'm keeping this one."),
    )),
}


def due(officer, done, told):
    """The next passage this officer's record has unlocked, or None.
    ``told`` holds the passage ids already told."""
    title, passages = FILES.get(officer, ("", ()))
    for threshold, passage in zip(THRESHOLDS, passages):
        if done < threshold:
            return None
        if passage[0] not in told:
            return passage
    return None


def heading(officer):
    title = FILES.get(officer, ("ORDER FILES", ()))[0]
    return f"ORDER FILES · {title.upper()}"


def page(officer, told):
    """The file as the ORDERS tab shows it: told passages and the locked rest."""
    title, passages = FILES.get(officer, ("", ()))
    rows = []
    for threshold, (passage_id, number, text) in zip(THRESHOLDS, passages):
        rows.append({"id": passage_id, "number": number, "text": text if passage_id in told else "",
                     "told": passage_id in told, "needs": threshold})
    return {"title": title, "passages": rows}
