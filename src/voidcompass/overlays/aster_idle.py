"""Officer's quiet watch: factual habits, kept voyages and heard story only."""
from datetime import datetime
import zlib

from voidcompass.overlays import aster_lore, watcher_habits, watcher_postcards


RECALL_REST_S = 30 * 86400
FACT_TOPICS = {"cmdr_record", "cmdr_power", "cmdr_squadron", "cmdr_carrier"}
RESTS = {"idle_postcard": watcher_postcards.RECALL_REST_S, "idle_moment": 6 * 3600,
         "aster_recall": 6 * 3600, "aster_lore_recall": 6 * 3600,
         "idle_aster_lore": 3 * 3600, "long_session": 3600}

PLAIN = {
    "cmdr_record": (
        "Your exploration record lists {systems} visited systems.",
        "The career log includes {systems} systems visited. A substantial set of arrivals.",
        "Your recorded career totals {jumps} hyperspace jumps.",
        "{jumps} jumps in the career record. I have noted the total.",
        "The career record includes {played} in flight.",
        "Recorded flight time: {played}. An appointment with some history behind it.",
    ),
    "idle_aster_lore": (
        "I have left space beneath today's entry. A voyage rarely follows the form exactly.",
        "An appointment is an ongoing duty. I am still learning the shape of this one.",
        "The manifest records who is aboard. Knowing the crew takes a little longer.",
        "There is room in this posting for more than a correct inventory.",
        "I prefer a report with room for a correction. It means someone is still paying attention.",
        "The crew register remains open. It is a record of people, rather than a finished task.",
    ),
    "aster_lore_recall": (
        "{c1}That first crew entry was an appointment, rather than an installation. The distinction still matters to me.",
        "{c1}I still leave space below a completed report. We spoke about why, when you accepted my appointment.",
        "{c2}Mara's second ledger gave names a place beside the cargo. I have kept the practice.",
        "{c2}Those early relief deliveries taught me to ask who was waiting, as well as what was due.",
        "{c3}The eleven-day wait changed what I considered a justified delay. The courier belonged in the account.",
        "{c3}Returning crew. Mara's correction to the spare berth was more useful than my original entry.",
        "{c4}The old arrival figures were correct. They still failed to account for Iven. I remember that distinction.",
        "{c4}Passage still owed. The captain's note deserved more attention than the completed cargo totals.",
        "{c5}Mara was right about the berth. Making room for someone need not require their return.",
        "{c5}Present crew. I added that page after learning not to make an old duty the purpose of your voyage.",
        "{c6}I signed the arrival certificate without rewriting what happened. A truthful account was enough.",
        "{c6}Officer on watch. The amended appointment leaves more room for the person I serve.",
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
    "aster_after": (
        "The old report is closed. The present watch still has room for another entry.",
        "Arrival certified. I find the duties that followed rather more interesting than the certificate.",
        "The second ledger remains open. There is a difference between finishing an account and ceasing to care.",
        "This ship has given me a present tense. I intend to make good use of it.",
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
    "idle_aster_lore": (
        "The blank space below the report remains deliberate. I have resisted the urge to label it.",
        "An appointment has duties. Fortunately, this one has also developed a view.",
        "I could make the register more efficient by removing the people. I regard that as a flaw in the proposal.",
    ),
    "aster_lore_recall": (
        "{c1}You accepted my appointment without a salary negotiation. I remain suspicious of how well that went.",
        "{c2}Mara improved the ledger without requesting a new form. An alarming precedent, and a useful one.",
        "{c3}I prepared eleven days of delay calculations. The courier's arrival rendered my presentation unnecessary.",
        "{c4}Every automated arrival check passed. It is an uncomfortable memory for an automated officer.",
        "{c5}Leave room. A standing order with exceptionally poor metrics and rather good judgement.",
        "{c6}The certificate survived my qualifications. I suspect it had no choice in the matter.",
    ),
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


def casual(topic):
    return (topic.startswith("idle_")
            or topic in {"quiet", "aster_after", "aster_recall", "aster_lore_recall", "long_session"}
            or topic.startswith("habit_") and topic != "habit_milestone")


def _key(kind, *values):
    value = repr((kind, *values)).encode("utf-8")
    return f"{kind}:{zlib.crc32(value):08x}"


def _fields(memory, key, at, now):
    from voidcompass.overlays.watcher_mind import when_text

    previous = memory.get("aster_idle_recalled", {}).get(key)
    if previous is not None and now - previous < RECALL_REST_S:
        return None
    try:
        when = when_text(datetime.fromtimestamp(float(at)).astimezone().isoformat(), now)
    except (OSError, OverflowError, TypeError, ValueError):
        return None
    return {"_recall": key, "when": when, "When": when[:1].upper() + when[1:]} if when else None


def choices(memory, rng, now):
    """Only use recorded facts. Recall identities rest across wording/restarts."""
    out = watcher_habits.choices(memory, 0, rng)
    activities = {"an explorer": "exploration", "a trader": "trade", "a miner": "mining",
                  "a fighter": "combat", "a courier": "courier work"}
    for topic, fields in out:
        if topic == "habit_style":
            fields["style"] = activities.get(fields["style"], fields["style"])
    heard = aster_lore.told(memory)
    if aster_lore.PASSAGES[0][0] in heard:
        out.append(("idle_aster_lore", {}))
    for index, chapter in enumerate(aster_lore.CHAPTERS):
        ids = [row[0] for row in aster_lore.PASSAGES if row[1] == chapter[0]]
        if all(key in heard for key in ids):
            at = max(heard[key] for key in ids)
            if now - at >= 86400:
                fields = _fields(memory, _key("chapter", index), at, now)
                if fields:
                    out.append(("aster_lore_recall", {**fields, f"c{index + 1}": ""}))
    for row in memory.get("postcards") or ():
        if not isinstance(row, (list, tuple)) or len(row) < 2 or not row[1]:
            continue
        try:
            old = now - float(row[0]) >= watcher_postcards.RECALL_AFTER_S
        except (TypeError, ValueError):
            continue
        fields = _fields(memory, _key("postcard", *row[:2]), row[0], now) if old else None
        if fields:
            out.append(("idle_postcard", {**fields, "place": str(row[1])}))
    for row in memory.get("aster_moments") or ():
        if not isinstance(row, dict) or not row.get("system"):
            continue
        try:
            old = now - float(row.get("at", now)) >= 2 * 86400
        except (TypeError, ValueError):
            continue
        event, system, station = row.get("event"), row["system"], row.get("station")
        # Several visits to one place form one memory, not a bank of repeatable announcements.
        fields = _fields(memory, _key("service", event, system, station), row.get("at"), now) if old else None
        if not fields:
            continue
        if event == "FSDJump":
            out.append(("aster_recall", {**fields, "system": system}))
            continue
        about = {"Docked": f"our docking at {station} in {system}" if station else "",
                 "MissionCompleted": f"a completed mission in {system}",
                 "SellExplorationData": f"the survey data we sold in {system}",
                 "MultiSellExplorationData": f"the survey data we sold in {system}",
                 "SellOrganicData": f"the biological data we sold in {system}"}.get(event)
        if about:
            out.append(("idle_moment", {**fields, "about": about, "About": about[:1].upper() + about[1:]}))
    rng.shuffle(out)
    return out
