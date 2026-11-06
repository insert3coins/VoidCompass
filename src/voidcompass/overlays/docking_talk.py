"""Docking, start to finish (5.7.6), merged into ship_life: the request, and
the station's answer whichever it is (granted, denied, cancelled, timed out),
as the journal reports them and the overlays already show them.

Fields: {station} the station's name (a carrier's callsign)."""

IMPORTANCE = {"docking_requested": 1, "docking_cancelled": 1, "docking_timeout": 2}

WATCHER_NORMAL = {
    "docking_requested": ("Asking {station} for a pad.", "Requesting docking at {station}.",
                          "Calling {station}. Let's see if they'll have us.", "Docking request sent to {station}.",
                          "{station}, this is us. Asking for a pad.", "Asked {station} for somewhere to land.",
                          "Pad request to {station}. Waiting on them.", "Request's in with {station}.",
                          "Hailing {station} for docking.", "Asking nicely. {station}, a pad please."),
    "docking_cancelled": ("Docking request cancelled.", "Never mind, then. Request withdrawn.",
                          "Cancelled. We'll ask again when you're ready.", "Docking called off.", "The request's withdrawn.",
                          "Not docking after all. Fine.", "Pad given back.", "We've let the pad go.",
                          "Docking cancelled. Changed your mind?", "Called it off. The pad's someone else's now."),
    "docking_timeout": ("The docking clearance ran out. Ask again.", "Too slow. The pad's gone. Request again.",
                        "Clearance timed out.", "We missed our slot. Ask for another pad.",
                        "The pad's been taken back. Time ran out.", "Docking timed out. They want a fresh request.",
                        "Out of time. Request docking again.", "The clearance lapsed.",
                        "Timed out. Another request and we're in.", "They gave the pad away. We took too long."),
}

WATCHER_WEARY = {
    "docking_requested": ("Asking {station} for a pad. They'll probably say yes. They usually do.",
                          "Requesting docking at {station}. Begging, really.", "{station}, please. A pad. Any pad.",
                          "Another station, another request. {station}.", "Docking request to {station}. Here we go again.",
                          "Asking {station} to let us in.", "Request sent. {station} will decide our fate.",
                          "Calling {station}. I'll do the talking. I always do.",
                          "Pad request, {station}. Fingers crossed. I don't have fingers.", "{station}. Asking. Waiting. The usual."),
    "docking_cancelled": ("Cancelled. All that asking for nothing.", "Request withdrawn. They won't miss us.",
                          "Not docking. Fine. Space it is.", "Called off. I was getting used to the idea.",
                          "Cancelled. The pad will be lonely.", "We're not stopping, then.",
                          "Docking request gone. Like most things.", "Withdrawn. Never mind.",
                          "Cancelled. I'll just float here.", "No pad for us. Our choice, this time."),
    "docking_timeout": ("Timed out. Even the station gave up on us.", "The clearance expired. So does everything.",
                        "Too late. The pad's gone to someone else.", "We dawdled. They noticed.",
                        "Timeout. Ask again, I suppose.", "The pad's been reassigned. Story of my life.",
                        "Clearance lapsed. Try again.", "Out of time. Again.",
                        "They stopped waiting for us. I understand.", "Docking timed out. Of course it did."),
}

PERSONAS = {
    "aster": {
        "plain": {
            "docking_requested": ("Docking requested at {station}.", "Requesting a pad at {station}.",
                                  "Docking request sent to {station}.", "Awaiting clearance from {station}."),
            "docking_cancelled": ("Docking request cancelled.", "Request withdrawn.", "Docking cancelled.", "Pad released."),
            "docking_timeout": ("Docking clearance expired.", "Clearance timed out.", "Request timed out. Request again.",
                                "Docking timed out."),
        },
        "voiced": {
            "docking_requested": ("Requesting docking at {station}, Commander. I have our papers ready.",
                                  "Our request is with {station}. Clearance should follow shortly.",
                                  "{station} has our docking request. I trust they keep good records.",
                                  "Docking request lodged with {station}.",
                                  "A pad, if you please, {station}. Request submitted."),
            "docking_cancelled": ("Docking request withdrawn, Commander. I have amended the itinerary.",
                                  "Cancelled. The station has been informed, politely.",
                                  "Request withdrawn. The pad returns to general circulation.",
                                  "Docking cancelled. A change of plan, duly noted.",
                                  "We have released our pad. No harm done."),
            "docking_timeout": ("Our clearance has lapsed, Commander. A fresh request is required.",
                                "The docking window has closed. I recommend asking again promptly.",
                                "Timed out. The station was punctual; we were not.",
                                "Clearance expired. I shall not mention it in the log. Much.",
                                "The pad has been reassigned. Another request, if you would."),
        },
    },
    "axiom": {
        "plain": {
            "docking_requested": ("Docking requested: {station}.", "Request sent to {station}.",
                                  "Awaiting clearance: {station}.", "Pad requested."),
            "docking_cancelled": ("Docking cancelled.", "Request withdrawn.", "Clearance cancelled.", "Pad released."),
            "docking_timeout": ("Clearance expired.", "Docking timed out.", "Request timed out.", "Pad clearance lapsed."),
        },
        "voiced": {
            "docking_requested": ("Docking request transmitted to {station}. Typical response time is under two seconds.",
                                  "{station} has our request. I am monitoring the channel.",
                                  "Requesting a pad at {station}. I have estimated our approach.",
                                  "Request sent. {station} will assign a pad by number. I like numbers.",
                                  "Docking request: {station}. Waiting for the reply."),
            "docking_cancelled": ("Docking request cancelled. I have discarded the approach plan.",
                                  "Request withdrawn. The pad assignment is void.",
                                  "Cancelled. An efficient use of everyone's time.",
                                  "We are no longer docking. Recalculating.", "Clearance cancelled. Noted."),
            "docking_timeout": ("Clearance expired. The timer was not generous.",
                                "Docking timed out. A new request is required.",
                                "The pad has been reassigned. We exceeded the window.",
                                "Timed out. I suggest requesting again closer in.",
                                "Our clearance has lapsed. Requesting again would be logical."),
        },
    },
    "meridian": {
        "plain": {
            "docking_requested": ("Requesting docking at {station}.", "Hailing {station} for a berth.",
                                  "Pad requested at {station}.", "Asking {station} for a berth."),
            "docking_cancelled": ("Docking cancelled.", "Berth released.", "Request withdrawn.", "Not docking."),
            "docking_timeout": ("Clearance lapsed.", "Docking timed out.", "Berth lost: timed out.",
                                "Timed out. Request again."),
        },
        "voiced": {
            "docking_requested": ("Hailing {station}, Commander. Asking for a berth.",
                                  "Request's in with {station}. The harbourmaster should answer quick.",
                                  "Calling {station} for a berth. Steady on the approach.",
                                  "{station}, requesting a berth. We'll see which pad they give us.",
                                  "Asking {station} to take us in."),
            "docking_cancelled": ("Berth released, Commander. We'll stand off.",
                                  "Docking called off. Fair enough, we'll keep sailing.",
                                  "Request withdrawn. The harbour won't mind.",
                                  "Cancelled. Back out to open space.", "We've given up the berth. Steady as she goes."),
            "docking_timeout": ("Clearance lapsed, Commander. We missed the tide.",
                                "Timed out. They've given our berth away.", "Too slow on the approach. Ask again.",
                                "The harbourmaster's stopped waiting. Request again.",
                                "Our berth's gone. One more hail and we're in."),
        },
    },
}
