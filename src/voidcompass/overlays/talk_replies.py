"""The officers' words for TALK's newer lookups (5.7.6): the nearest station
with a service, and how far to a system. Merged into each officer's commands
(the Watcher's are in watcher_copilot.REPLIES)."""

OFFICERS = {
    "aster": {
        "station_opening": ("Locating the nearest {label}, Commander. One moment.",
                            "Consulting the station registry for the nearest {label}.",
                            "Requesting the nearest {label} through the uplink.",
                            "The nearest {label}: I shall have it for you shortly."),
        "distance_opening": ("{name} is not in our own log, Commander. Asking the uplink.",
                             "Checking the charts for {name}. A moment, please.",
                             "Our log has no entry for {name}. I am requesting its position.",
                             "Looking up {name}, Commander. The uplink will know."),
        "distance_unknown": ("I have no record of {name}, Commander. With trading searches enabled in Settings, under "
                             "Integrations, I can look it up.",
                             "{name} is not in our log. Enable trading searches in Settings, under Integrations, and I "
                             "shall find it.",
                             "We have never been to {name}, so I have no position for it. Trading searches, in Settings "
                             "under Integrations, would let me look it up.",
                             "No entry for {name} in the log, Commander. The uplink could find it, once trading searches "
                             "are on in Settings, under Integrations."),
        "distance_nowhere": ("Our own position is not yet on record, Commander. Ask again after the next jump.",
                             "I cannot measure from an unrecorded position. One jump, and I shall have it.",
                             "The log does not yet show where we are. Ask me again after the next jump.",
                             "Our present position is missing from the record. A jump will supply it."),
    },
    "axiom": {
        "station_opening": ("Searching for the nearest {label}.", "Querying the station data for the nearest {label}.",
                            "Locating the nearest {label}. One moment.", "The nearest {label}: searching."),
        "distance_opening": ("{name} is not in my records. Querying the uplink.", "Looking up the coordinates of {name}.",
                             "No coordinates for {name} locally. Asking the uplink.", "Resolving {name}. One moment."),
        "distance_unknown": ("I have no coordinates for {name}. Enable trading searches in Settings, under Integrations, "
                             "and I can look it up.",
                             "{name} is not in my records. With trading searches on, in Settings under Integrations, I "
                             "can query it.",
                             "Unknown system: {name}. Trading searches, in Settings under Integrations, would let me "
                             "look it up.",
                             "I cannot place {name} from our own data. Turn on trading searches in Settings, under "
                             "Integrations."),
        "distance_nowhere": ("I do not have our position yet. Ask again after the next jump.",
                             "Our position is unknown. One jump will fix it.",
                             "No position recorded yet. Ask me after the next jump.",
                             "I need our coordinates first. The next jump will supply them."),
    },
    "meridian": {
        "station_opening": ("Finding the nearest {label}, Commander.", "Checking the charts for the nearest {label}.",
                            "Nearest {label}, coming up. One moment.", "Looking for the nearest {label}. Stand by."),
        "distance_opening": ("{name}'s not on my charts yet. Asking the uplink.", "Plotting where {name} lies. A moment.",
                             "I haven't got {name} charted. Asking the uplink.", "Looking up {name}'s position, Commander."),
        "distance_unknown": ("I haven't got {name} charted. Turn on trading searches in Settings, under Integrations, "
                             "and I'll look it up.",
                             "{name}'s not on my charts. With trading searches on, in Settings under Integrations, I can "
                             "find it.",
                             "We've never sailed to {name}, so I've no fix on it. Trading searches, in Settings under "
                             "Integrations, would let me look.",
                             "No chart for {name}, Commander. Switch on trading searches in Settings, under Integrations, "
                             "and I'll find it."),
        "distance_nowhere": ("I haven't got a fix on our position yet. Ask me after the next jump.",
                             "No fix on where we are yet. One jump and I'll have it.",
                             "Our position's not on the chart yet. Ask again after the next jump.",
                             "I need a fix first, Commander. The next jump will give me one."),
    },
    "lyra": {
        "station_opening": ("Searching for the nearest {label}. One moment.", "Finding the nearest {label}, Commander.",
                            "Querying the uplink for the nearest {label}.", "Nearest {label}, coming up."),
        "distance_opening": ("{name} is not in our own logs. Asking the uplink.", "Looking up {name}. One moment.",
                             "No coordinates for {name} aboard. Querying the uplink.", "Resolving {name}, Commander."),
        "distance_unknown": ("I have no coordinates for {name}. Turn on trading searches in Settings, under Integrations, "
                             "and I can look it up.",
                             "{name} is not in our logs. With trading searches on, in Settings under Integrations, I can find it.",
                             "We have never been to {name}, so I cannot place it. Trading searches, in Settings under "
                             "Integrations, would let me look.",
                             "No record of {name} aboard. Switch on trading searches in Settings, under Integrations, "
                             "and I will find it."),
        "distance_nowhere": ("I do not have our position yet. Ask again after the next jump.",
                             "Our position is not logged yet. One jump will fix it.",
                             "No position fix yet. Ask me after the next jump.",
                             "I need our coordinates first, Commander. The next jump will give them to me."),
    },
}
