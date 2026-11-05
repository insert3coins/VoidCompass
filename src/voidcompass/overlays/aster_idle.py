"""Officer's quiet watch: factual habits, kept voyages and heard story only."""
from voidcompass.overlays import companion_idle
from voidcompass.overlays.companion_idle import RECALL_REST_S, FACT_TOPICS, RESTS, casual  # noqa: F401


PLAIN = {
    "cmdr_record": (
        "Your exploration record lists {systems} visited systems.",
        "The career log includes {systems} systems visited. A substantial set of arrivals.",
        "Your recorded career totals {jumps} hyperspace jumps.",
        "{jumps} jumps in the career record. I have noted the total.",
        "The career record includes {played} in flight.",
        "Recorded flight time: {played}. An appointment with some history behind it.",
    ),
    "idle_postcard": (
        "The postcard from {place} is still in our voyage record. We took it {when}.",
        "I was reviewing our postcard from {place}, {when}. A useful reminder of the journey itself.",
        "{When}, we kept an image of {place}. I have retained its place in the archive.",
        "The itinerary gives {place} a line. The postcard gives it rather more.",
        "Our image from {place} has survived the intervening watches. Taken {when}.",
        "{place}, {when}. Some entries are worth keeping in colour.",
        "There is a postcard of {place} among our records. I paused over it on this watch.",
        "I found the image we kept at {place}, {when}. A pleasant addition to the voyage account.",
    ),
    "aster_recall": (
        "We reached {system} {when}. I have kept the arrival in our service record.",
        "{system}, {when}. A destination from an earlier watch.",
        "I was reviewing the passage through {system}, {when}. Our route has acquired some history.",
        "The log still holds our arrival at {system}. That was {when}.",
        "An earlier entry caught my attention: {system}, {when}.",
        "I have retained {system} in the voyage account. We were there {when}.",
    ),
    "idle_moment": (
        "The service record includes {about}, {when}. Worth retaining beyond the totals.",
        "{When}, we recorded {about}. I was looking back through that watch.",
        "A note from an earlier watch: {about}. That was {when}.",
        "I have kept an entry about {about}, {when}.",
        "{About}, {when}. A particular moment in an otherwise very long account.",
        "The summary omits the small details. My record still includes {about}, {when}.",
    ),
    "habit_flight": (
        "Our flight record stands at {jumps} jumps over {ly} light years.",
        "The longest recorded jump in my watch is {longest} light years, across {jumps} jumps in total.",
        "I have logged {scoops} fuel scoops, supplying {scooped_t} tonnes along the route.",
        "{landings} recorded landings. The surface portions deserve their place in the voyage account.",
        "The flight log includes {low_fuel} low-fuel warnings. Allow a margin on the next leg.",
        "Our recorded jumps most often lead to {star}. A familiar entry in the watch log.",
    ),
    "habit_scans": (
        "You have given {bodies} bodies a place in the survey record.",
        "{firsts} first discoveries in our records. Those observations began with you.",
        "I have logged {mapped} mapped worlds. A worthwhile improvement to the charts.",
        "Of {mapped} mapping surveys, {efficient} earned the efficiency bonus.",
        "Our biology record contains {bio} completed analyses. Patient work, properly accounted for.",
        "{bodies} scanned bodies. The route has become a survey as well as a passage.",
    ),
    "habit_cargo": (
        "The mining record includes {mined_n} tonnes of {mined}.",
        "{commodity} leads our recorded loading and refining totals, at {tonnes} tonnes.",
        "We have purchased {limpets} limpets. A considerable provision for the supporting work.",
        "{mined_n} tonnes of {mined}, refined. There is quite a watch behind that figure.",
        "The cargo account has become familiar with {commodity}: {tonnes} tonnes recorded.",
        "{limpets} limpets purchased. Small provisions can account for a great deal of work.",
    ),
    "habit_combat": (
        "The record holds {bounties} bounty claims, worth {bounty_cr} credits.",
        "{target} appears in {target_n} recorded bounty claims. I have retained the detail.",
        "Our watch has recorded {interdicted} interdictions. An argument for keeping the departure plan flexible.",
        "{escaped} successful escapes from {interdicted} interdictions. Leaving can be a sound decision.",
        "I have logged {bonds} combat bond claims. The service record includes the difficult watches too.",
        "{bounties} bounty claims. I would prefer our next accomplishments to involve less incoming fire.",
    ),
    "habit_trade": (
        "{sold} leads our recorded sales, at {sold_t} tonnes.",
        "Recorded trading profit stands at {profit} credits. A useful provision for future departures.",
        "Our best recorded trade was {best}, returning {best_cr} credits.",
        "We have sold {sold_t} tonnes of {sold}. That commodity has earned a page in the accounts.",
        "The trading account shows {profit} credits in profit. Worth keeping the figures accurate.",
        "{best} remains the best trade in my record: {best_cr} credits.",
    ),
    "habit_style": (
        "Your recorded work leans towards {style}, at {share} percent of the activity counted.",
        "{style} accounts for {share} percent of your recorded activity. I am learning the shape of your posting.",
        "The service figures suggest a preference for {style}: {share} percent so far.",
        "Our log gives {style} the largest share, at {share} percent. An observation, rather than an assignment.",
    ),
}

DRY = {
    "idle_postcard": (
        "{place}, {when}. The postcard is a rather better report than my coordinates.",
        "I reviewed the postcard from {place}. No discrepancy found between the archive and my fondness for it.",
        "Our postcard from {place} is still filed correctly. You may consider this an unusually scenic audit.",
        "The image from {place} has no immediate operational value. I have kept it for precisely that reason.",
    ),
    "aster_recall": (
        "{system}, {when}. The log has become long enough to justify a less severe filing system.",
        "I revisited {system} in the records. {When}. A considerably cheaper method of travel.",
        "{system} remains in the arrival column. I am pleased that the column has developed some character.",
    ),
    "idle_moment": (
        "{About}, {when}. The summary would reduce that to a number. I have declined to cooperate.",
        "I kept the note about {about}. An entirely defensible use of archival space.",
        "{When}: {about}. The duty log occasionally provides its own entertainment.",
    ),
    "habit_flight": ("{jumps} jumps. Our itinerary is making a persuasive case for additional stationery.",
                     "{scoops} fuel scoops. A remarkably large number of stops without a receipt."),
    "habit_scans": ("{bodies} bodies scanned. The charts are becoming difficult to impress.",
                    "{mapped} mapped worlds. I appreciate a report with this much supporting evidence."),
    "habit_cargo": ("{limpets} limpets purchased. The provisioning account has become a rather crowded crew list.",
                    "{tonnes} tonnes of {commodity}. The manifest recognises a recurring character."),
    "habit_combat": ("{bounties} bounty claims. The accounts approve; the repair estimates may have reservations.",
                     "{interdicted} interdictions. Other pilots appear reluctant to respect our schedule."),
    "habit_trade": ("{profit} credits in trading profit. A number that requires very little editorial assistance.",
                    "{sold_t} tonnes of {sold}. Our relationship with that commodity has become professionally significant."),
    "habit_style": ("{style}, {share} percent. I have filed that under preference, pending your next complete change of plan.",
                    "The figures favour {style} at {share} percent. I shall refrain from ordering a commemorative plaque."),
}



def choices(memory, rng, now, story=None):
    from voidcompass.overlays import aster_lore
    return companion_idle.choices(memory, rng, now, story or aster_lore.STORY)
