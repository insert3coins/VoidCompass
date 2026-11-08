"""Passing an order on (5.7.7). An officer off watch speaks in its own voice
or not at all, and its voice may be off or not downloaded. Then, if the
companion on watch can speak, it passes the order on in its own words, so a
commander with only one voice installed still hears every order. Fields:
{officer} (who it's from) and {title}."""

RELAY = {
    "watcher": {
        "normal": {
            "relay_offer": ("{officer} has an order for you. {title}. It's on the deck.", "{officer} wants something. {title}.",
                            "An order from {officer}: {title}.", "{officer} asked me to tell you. {title}.",
                            "{officer} has an order. {title}. Look at the deck."),
            "relay_done": ("{officer} says {title} is done.", "{title}. Done. {officer} is pleased.",
                           "{officer}'s order is finished. {title}.", "Done, {officer} says. {title}.",
                           "{title}. {officer} wanted you to know it's done."),
            "relay_news": ("Word from {officer} about {title}.", "{officer} has news on {title}. It's on the deck.",
                           "{officer} says there's progress. {title}.", "{title}. {officer} has an update.",
                           "Something from {officer} about {title}."),
        },
        "weary": {
            "relay_offer": ("{officer} has an order for you. {title}. Of course they do.", "{officer} wants something from you. {title}. Naturally.",
                            "An order from {officer}. {title}. I'm only passing it on.",
                            "{officer} asked me to tell you. {title}. So I'm telling you.",
                            "{officer} has an order. {title}. It's on the deck, if you care."),
            "relay_done": ("{officer} says {title} is done. They're pleased. Someone should be.",
                           "{title}. Done. {officer} will be insufferable.", "{officer}'s order is finished. {title}. Somebody's happy.",
                           "Done, {officer} says. {title}. Well done, I suppose.", "{title}. Finished. {officer} wanted you told."),
            "relay_news": ("Word from {officer}. {title}. I said I'd pass it on.", "{officer} has news. {title}. The deck has it, if you care.",
                           "{officer} says there's progress. {title}. Imagine.", "{title}: {officer} updated it. Thrilling.",
                           "Something from {officer}. {title}. I'm just the messenger."),
        },
    },
    "aster": {
        "plain": {
            "relay_offer": ("Order from {officer}: {title}.", "{officer} has an order: {title}.", "Relayed from {officer}: {title}.",
                            "{officer}: new order. {title}."),
            "relay_done": ("{officer} reports {title} complete.", "{title}: done, per {officer}.", "Complete: {title}. From {officer}.",
                           "{officer}: {title} closed."),
            "relay_news": ("Update from {officer}: {title}.", "{officer} reports on {title}.", "{title}: update from {officer}.",
                           "Relayed: {officer} on {title}."),
        },
        "voiced": {
            "relay_offer": ("{officer} has an order for you, Commander: {title}. It's on the deck.",
                            "Relaying from {officer}: {title}. I've put the particulars on the deck.",
                            "An order from {officer}, Commander. {title}.", "{officer} asked me to pass this on: {title}.",
                            "On behalf of {officer}: {title}. Details on the deck."),
            "relay_done": ("{officer} reports {title} complete, Commander. Well done.", "Word from {officer}: {title} is finished.",
                           "{title} is done, {officer} tells me. I've entered it.", "Complete, per {officer}: {title}.",
                           "{officer} asks me to say {title} is done. With some enthusiasm."),
            "relay_news": ("An update from {officer} on {title}.", "{officer} reports progress on {title}. On the deck.",
                           "Relaying from {officer}: news on {title}.", "{officer} has an update on {title}, Commander.",
                           "{title}: {officer} has word. The deck has it."),
        },
    },
    "axiom": {
        "plain": {
            "relay_offer": ("Order from {officer}: {title}.", "{officer}: {title}.", "Relayed: {officer}, {title}.",
                            "{officer} proposes {title}."),
            "relay_done": ("{officer}: {title} complete.", "{title} done, per {officer}.", "Complete: {title} ({officer}).",
                           "{officer} confirms {title}."),
            "relay_news": ("{officer} on {title}: update.", "Update from {officer}.", "{title}: {officer} reports.",
                           "Relayed update: {title}."),
        },
        "voiced": {
            "relay_offer": ("{officer} has an order for you: {title}. I've put it on the deck.",
                            "Relaying from {officer}: {title}.", "{officer} proposes {title}. The details are on the deck.",
                            "An order from {officer}. {title}. Their voice is off, so I'm reading it.",
                            "{officer} would like you to consider {title}."),
            "relay_done": ("{officer} reports {title} complete. I've added it to the record.", "{title}: done, {officer} says.",
                           "Complete: {title}. {officer} is pleased; I can tell from the logs.",
                           "{officer}'s order, {title}, is finished.", "{title} is done. {officer} wanted you to know."),
            "relay_news": ("{officer} has an update on {title}.", "Progress on {title}, from {officer}.",
                           "Relaying: {officer} on {title}.", "{title}: {officer} reports progress. On the deck.",
                           "An update for {title}, via {officer}."),
        },
    },
    "meridian": {
        "plain": {
            "relay_offer": ("Order from {officer}: {title}.", "{officer} has an order: {title}.", "From {officer}: {title}.",
                            "{officer}: {title}."),
            "relay_done": ("{officer}: {title} done.", "{title} complete, says {officer}.", "Done: {title}.",
                           "{officer} reports {title} done."),
            "relay_news": ("{officer} on {title}.", "Update: {title}.", "From {officer}: news on {title}.",
                           "{officer} has word on {title}."),
        },
        "voiced": {
            "relay_offer": ("{officer} has an order for you, Commander: {title}. It's on the deck.",
                            "Passing word from {officer}: {title}.", "An order from {officer}. {title}. Details on the chart table.",
                            "{officer} asked me to pass it along: {title}.", "Word from {officer}, Commander. {title}."),
            "relay_done": ("{officer} says {title} is done. Well sailed.", "{title}: complete, by {officer}'s reckoning.",
                           "Word from {officer}: {title}, finished.", "{officer} reports {title} done, Commander.",
                           "{title} is done. {officer}'s very pleased."),
            "relay_news": ("{officer} has word on {title}, Commander.", "News from {officer} on {title}. It's on the deck.",
                           "Passing it on: {officer} on {title}.", "{officer} reports progress on {title}.",
                           "An update from {officer}, Commander. {title}."),
        },
    },
    "lyra": {
        "plain": {
            "relay_offer": ("Order from {officer}: {title}.", "{officer}: {title}.", "Relayed order: {title}.",
                            "{officer} has an order: {title}."),
            "relay_done": ("{officer}: {title} complete.", "{title}: done, per {officer}.", "Complete: {title}.",
                           "{officer} reports {title} done."),
            "relay_news": ("Fresh update from {officer}: {title}.", "{officer} reports on {title}.", "{title}: update.",
                           "Relayed: {officer} on {title}."),
        },
        "voiced": {
            "relay_offer": ("{officer} has an order for you! {title}. It's on the deck.",
                            "Passing on an order from {officer}: {title}.", "{officer}'s voice is off, so I'll read it: {title}.",
                            "An order from {officer}. {title}. Details on the deck.", "{officer} wants to know: {title}?"),
            "relay_done": ("{officer} says {title} is done! Logging it in bold.", "Word from {officer}: {title}, finished.",
                           "{title}: complete. {officer} is very pleased.", "{officer}'s order is done. {title}.",
                           "Done! {title}, per {officer}."),
            "relay_news": ("{officer} has news on {title}.", "Update from {officer}: {title}.", "Passing it on: {officer} on {title}.",
                           "{title}: progress, says {officer}.", "{officer} has an update. {title}."),
        },
    },
}
