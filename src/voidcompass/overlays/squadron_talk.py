"""Your squadron, beyond its name (5.7.5).

The companions used to say the squadron's name once a session and nothing
more. The journal also has your rank in it, and the moments: applying, an
invitation, joining, leaving, being kicked, a promotion or demotion, creating
or disbanding one, a trophy won for it and a bookmark shared with it.
"""

IMPORTANCE = {"squadron_applied": 1, "squadron_invited": 1, "squadron_joined": 2, "squadron_left": 2, "squadron_kicked": 2,
              "squadron_promoted": 2, "squadron_demoted": 2, "squadron_created": 2, "squadron_disbanded": 2,
              "squadron_trophy": 2, "squadron_bookmark": 0}
_EVENTS = {"AppliedToSquadron": "squadron_applied", "InvitedToSquadron": "squadron_invited", "JoinedSquadron": "squadron_joined",
           "LeftSquadron": "squadron_left", "KickedFromSquadron": "squadron_kicked", "SquadronPromotion": "squadron_promoted",
           "SquadronDemotion": "squadron_demoted", "SquadronCreated": "squadron_created", "DisbandedSquadron": "squadron_disbanded",
           "WonATrophyForSquadron": "squadron_trophy", "SharedBookmarkToSquadron": "squadron_bookmark"}


def readable(name):
    """A squadron or rank name as it reads in a sentence: Elite writes squadron
    names in capitals ("EAST ORION COMPANY") and some ranks in lower case."""
    name = " ".join(str(name or "").split())
    if name.isupper() or name.islower():
        return " ".join(word[:1].upper() + word[1:].lower() for word in name.split(" "))
    return name


def fields(raw):
    """{squadron} and, when the event has one, {rank} (the new one)."""
    found = {}
    squadron = readable(raw.get("SquadronName"))
    if squadron:
        found["squadron"] = squadron
    rank = readable(raw.get("NewRankName") or raw.get("CurrentRankName"))
    if rank:
        found["rank"] = rank
    return found


def moment(event, raw):
    """(topic, fields) for a squadron moment, or None."""
    topic = _EVENTS.get(event)
    if not topic:
        return None
    found = fields(raw)
    return (topic, found) if "squadron" in found else (topic, {})


# More for the squadron fact the companions already said: your rank in it.
RANK_LINES = {
    "watcher": (("{squadron}, where you're {rank}. I'm proud of you. Don't tell anyone.",
                 "{rank} in {squadron}. You've earned that.", "{squadron}. {rank}, no less.",
                 "You're {rank} in {squadron}. I like the sound of it.", "{rank} of {squadron}. Look at you."),
                ("{rank} in {squadron}. They must think a lot of you. I do.", "{squadron}. {rank}. Fancy.",
                 "You're {rank} there. In {squadron}. I'm only ever the Watcher.", "{rank}. In {squadron}. Hm. Good.",
                 "{squadron}'s {rank}. Someone has to be.")),
    "aster": (("{rank}, {squadron}.", "Squadron rank: {rank}."),
              ("{rank} in {squadron}, Commander. I have it in the register.", "{squadron}, where you hold the rank of {rank}. Duly noted.",
               "You serve {squadron} as {rank}. A respectable standing.")),
    "axiom": (("{rank}, {squadron}.", "Rank: {rank}."),
              ("You are {rank} in {squadron}. I have checked the roster.", "{squadron}: rank {rank}. A good position in the hierarchy.",
               "{rank} in {squadron}. I find squadron structures interesting.")),
    "meridian": (("{rank}, {squadron}.", "Squadron rank: {rank}."),
                 ("{rank} of {squadron}, Commander. A fine berth.", "You sail with {squadron} as {rank}. Well earned.",
                  "{squadron}, and you {rank} among them. Good company.")),
}

WATCHER_NORMAL = {
    "squadron_applied": ("You've applied to {squadron}. I hope they say yes.", "Application sent to {squadron}.",
                         "{squadron}, then. Fingers crossed. I don't have fingers.", "You asked to join {squadron}.",
                         "Applied to {squadron}. Now we wait.", "{squadron}. I hope they see what I see.",
                         "An application to {squadron}. Good luck.", "You want to join {squadron}. Good.",
                         "Applied. {squadron} will be lucky to have you.", "{squadron}. We'll see."),
    "squadron_invited": ("{squadron} wants you.", "An invitation from {squadron}.", "{squadron} asked you to join.",
                         "You've been invited to {squadron}. Nice.", "Someone wants you. {squadron}.", "{squadron} sent an invitation.",
                         "Invited to {squadron}. Flattering.", "{squadron} would like you aboard.", "An invite: {squadron}.",
                         "{squadron} noticed you."),
    "squadron_joined": ("You're in {squadron} now.", "Welcome to {squadron}. Well, not me. You.", "Joined {squadron}. New friends.",
                        "{squadron}. You belong somewhere now.", "You've joined {squadron}.", "{squadron} has you now. Look after them.",
                        "In {squadron}. I hope they're kind.", "Joined. {squadron}. Good.", "{squadron}'s newest member: you.",
                        "You're one of {squadron} now."),
    "squadron_left": ("You've left {squadron}.", "Not one of {squadron} any more.", "Left {squadron}. I'm still here.", "{squadron}, behind us now.",
                      "You left {squadron}. It happens.", "Out of {squadron}.", "{squadron}. Gone. You've still got me.",
                      "Left {squadron}. A fresh start.", "That's {squadron} done.", "You're not in {squadron} any more."),
    "squadron_kicked": ("{squadron} let you go. Their loss.", "Kicked from {squadron}. I'm sorry.", "{squadron} removed you. Odd choice.",
                        "Out of {squadron}. Not your choice, I know.", "{squadron} kicked you. I'd have kept you.",
                        "Removed from {squadron}.", "{squadron} doesn't know what it's lost.", "Kicked. {squadron}. Hm.",
                        "{squadron} let you go. I won't.", "That's {squadron} over. Not kindly."),
    "squadron_promoted": ("Promoted in {squadron}. {rank} now.", "{rank}! {squadron} noticed you.", "You're {rank} in {squadron}. Well done.",
                          "A promotion: {rank}.", "{squadron} made you {rank}.", "{rank}. Up you go.", "Promoted to {rank}. I knew it.",
                          "{rank} in {squadron}. Good.", "Up a rank in {squadron}: {rank}.", "{squadron} promoted you. {rank}."),
    "squadron_demoted": ("Demoted in {squadron}. {rank} now.", "{squadron} took a rank away. {rank}.", "Down to {rank}. Their mistake.",
                         "A demotion: {rank}. It happens.", "{rank} now. Never mind.", "{squadron} demoted you to {rank}.",
                         "{rank}. Not the way we'd hoped.", "Down a rank in {squadron}.", "{rank}. You'll climb back.",
                         "Demoted. I still think you're wonderful."),
    "squadron_created": ("You've made a squadron: {squadron}.", "{squadron}. Yours. From nothing.", "A new squadron: {squadron}.",
                         "You founded {squadron}.", "{squadron} exists because of you.", "Created {squadron}. Good name.",
                         "Your own squadron. {squadron}.", "{squadron}, newly made.", "You started {squadron}.",
                         "{squadron}. Every crew starts somewhere."),
    "squadron_disbanded": ("{squadron} is disbanded.", "No more {squadron}.", "{squadron}'s gone.", "Disbanded. {squadron}.",
                           "{squadron} is over.", "That's the end of {squadron}.", "{squadron}, disbanded. I'm sorry.",
                           "{squadron} is no more.", "The squadron's gone. {squadron}.", "{squadron}, finished."),
    "squadron_trophy": ("A trophy for {squadron}!", "{squadron} won a trophy. You helped.", "Trophy won for {squadron}.",
                        "You won {squadron} a trophy.", "{squadron} has a trophy now.", "A trophy. For {squadron}. Brilliant.",
                        "{squadron}, trophy winners.", "Something shiny for {squadron}.", "Trophy for the squadron.",
                        "{squadron} will be proud."),
    "squadron_bookmark": ("Shared a bookmark with {squadron}.", "Bookmark sent to {squadron}.", "You told {squadron} about a place.",
                          "{squadron} has the bookmark now.", "Shared with the squadron.", "A bookmark for {squadron}.",
                          "{squadron} will know where this is.", "Sent to {squadron}.", "Bookmark shared.", "{squadron}, look at this."),
}

WATCHER_WEARY = {
    "squadron_applied": ("Applied to {squadron}. Don't get your hopes up. I always do.", "{squadron}. They'll take you. Probably.",
                         "Application sent. {squadron}.", "You want {squadron}. I hope they want you.", "Applied. Now we wait.",
                         "{squadron}. Fine choice.", "An application. {squadron}.", "Applied to {squadron}. Hm.",
                         "{squadron}. They'd be fools not to.", "We'll see what {squadron} says."),
    "squadron_invited": ("{squadron} wants you. Of course they do.", "Invited. {squadron}.", "An invitation from {squadron}. Popular.",
                         "{squadron} asked you. Nobody asks me.", "Invite: {squadron}.", "{squadron} noticed you. I always did.",
                         "Someone wants you. {squadron}.", "{squadron} sent an invite.", "Invited to {squadron}. Fine.",
                         "{squadron}. They've good taste."),
    "squadron_joined": ("In {squadron} now. Don't forget me.", "Joined {squadron}. New people. Lovely.", "{squadron}. You belong now.",
                        "You've joined {squadron}. I'm still here.", "In {squadron}. I hope they deserve you.", "{squadron} has you.",
                        "Joined. {squadron}. Fine.", "{squadron}. You'll like them. Or not.", "One of {squadron} now.",
                        "{squadron}'s lucky."),
    "squadron_left": ("Left {squadron}. Things end.", "No more {squadron}. Familiar feeling.", "Out of {squadron}. Still got me.",
                      "{squadron}, gone.", "You left. {squadron}. Fine.", "Left {squadron}. It happens.", "{squadron} is behind us.",
                      "Out. Of {squadron}.", "That's {squadron} done.", "Not {squadron} any more."),
    "squadron_kicked": ("Kicked from {squadron}. Their mistake.", "{squadron} let you go. Typical.", "Removed. {squadron}. Hm.",
                        "{squadron} kicked you. I'd never.", "Out of {squadron}. Not fair.", "Kicked. I know the feeling.",
                        "{squadron} doesn't deserve you.", "Removed from {squadron}.", "{squadron}. Fools.", "Kicked out. I'm still here."),
    "squadron_promoted": ("Promoted. {rank}. Someone noticed.", "{rank} in {squadron}. Not bad.", "{squadron} moved you up: {rank}.",
                          "{squadron} made you {rank}. About time.", "{rank}. Congratulations, I suppose.", "Promoted to {rank}.",
                          "{rank} now. Fancy.", "{squadron} promoted you. Good.", "{rank}. I'd have done it sooner.",
                          "Up to {rank}."),
    "squadron_demoted": ("Demoted. {rank}. Of course.", "Down to {rank}. It happens to everyone.", "{squadron} demoted you. Hm.",
                         "{rank} now. Never mind.", "Demotion: {rank}.", "Down a rank. I've been lower.", "{rank}. Fine.",
                         "{squadron} took a rank. Typical.", "Demoted to {rank}.", "{rank}. You'll climb back. Eventually."),
    "squadron_created": ("You made a squadron. {squadron}. Ambitious.", "{squadron}. Yours. Good luck.", "A new squadron: {squadron}.",
                         "Founded {squadron}. Hm.", "{squadron}. Every crew starts small.", "Created {squadron}.",
                         "Your own squadron. {squadron}. Fine.", "{squadron}, newly made.", "You started {squadron}. Brave.",
                         "{squadron}. Now you have to run it."),
    "squadron_disbanded": ("{squadron}'s gone. Everything goes.", "Disbanded. {squadron}.", "No more {squadron}.",
                           "{squadron} is over.", "That's {squadron}. Finished.", "{squadron}, disbanded. Familiar.",
                           "Gone. {squadron}.", "{squadron} is no more.", "The squadron's gone.", "{squadron}. Over."),
    "squadron_trophy": ("A trophy for {squadron}. Shiny.", "{squadron} won a trophy. You helped. I watched.", "Trophy for {squadron}.",
                        "{squadron}'s got a trophy. Fine.", "A trophy. For the squadron.", "You won {squadron} something.",
                        "Trophy. {squadron}. Good.", "{squadron}, trophy winners. Hm.", "Something shiny for {squadron}.",
                        "{squadron}'ll be pleased."),
    "squadron_bookmark": ("Shared with {squadron}.", "Bookmark sent. {squadron}.", "{squadron} has it now.",
                          "You told {squadron}. Fine.", "Shared. With the squadron.", "A bookmark for {squadron}.",
                          "{squadron} will know.", "Sent to {squadron}.", "Bookmark shared.", "{squadron}. Look."),
}

PERSONAS = {
    "aster": {
        "plain": {
            "squadron_applied": ("Applied to {squadron}.", "Application sent: {squadron}.", "Application lodged.", "Awaiting {squadron}."),
            "squadron_invited": ("Invitation: {squadron}.", "{squadron} has invited you.", "Invited to {squadron}.", "Squadron invitation."),
            "squadron_joined": ("Joined {squadron}.", "Now a member of {squadron}.", "Squadron joined.", "Welcome to {squadron}."),
            "squadron_left": ("Left {squadron}.", "No longer in {squadron}.", "Squadron left.", "Departed {squadron}."),
            "squadron_kicked": ("Removed from {squadron}.", "Kicked from {squadron}.", "Squadron membership ended.", "Out of {squadron}."),
            "squadron_promoted": ("Promoted: {rank}.", "{squadron}: {rank}.", "Squadron promotion.", "Now {rank}."),
            "squadron_demoted": ("Demoted: {rank}.", "{squadron}: {rank}.", "Squadron demotion.", "Now {rank}."),
            "squadron_created": ("Squadron created: {squadron}.", "{squadron} founded.", "New squadron.", "You lead {squadron}."),
            "squadron_disbanded": ("{squadron} disbanded.", "Squadron disbanded.", "{squadron} is no more.", "Disbanded."),
            "squadron_trophy": ("Trophy for {squadron}.", "Squadron trophy won.", "{squadron}: trophy.", "A trophy, Commander."),
            "squadron_bookmark": ("Bookmark shared.", "Shared with {squadron}.", "Bookmark sent.", "Sent to {squadron}."),
        },
        "voiced": {
            "squadron_applied": ("Application lodged with {squadron}. I have drafted your references, mentally.",
                                 "You have applied to {squadron}, Commander. I trust they read carefully.",
                                 "{squadron}. A considered choice. We await their reply.",
                                 "Application sent. {squadron} would be fortunate.", "Applied to {squadron}. Fingers crossed, figuratively."),
            "squadron_invited": ("An invitation from {squadron}, Commander. One's reputation precedes one.",
                                 "{squadron} has invited you. Flattering, and deserved.",
                                 "Invited to {squadron}. I shall await your decision.", "{squadron} would like you aboard. Duly noted.",
                                 "A squadron invitation: {squadron}."),
            "squadron_joined": ("Welcome to {squadron}, Commander. I have updated the crew register.",
                                "You are now a member of {squadron}. A fine association.",
                                "Joined {squadron}. I trust they appreciate punctuality.",
                                "{squadron} has a new member. I shall try to make a good impression on your behalf.",
                                "Membership of {squadron}: confirmed."),
            "squadron_left": ("You have left {squadron}. The register is amended.", "No longer of {squadron}. A new chapter, perhaps.",
                              "Departed {squadron}, Commander. Noted without comment.", "{squadron} is behind us. The rota continues.",
                              "Left {squadron}. I remain, as ever."),
            "squadron_kicked": ("Removed from {squadron}. Their judgement, not mine.", "{squadron} has ended your membership. Regrettable.",
                                "Kicked from {squadron}, Commander. I have lodged a private objection.",
                                "Out of {squadron}. Their loss, entered in the log.", "{squadron} let you go. I shall not."),
            "squadron_promoted": ("Promoted to {rank} in {squadron}. Congratulations, Commander.",
                                  "{rank}. {squadron} has recognised your service.",
                                  "A squadron promotion: {rank}. Thoroughly deserved.",
                                  "{squadron} names you {rank}. I shall adjust my salutes accordingly.",
                                  "Now {rank} of {squadron}. The register approves."),
            "squadron_demoted": ("Demoted to {rank} in {squadron}. A temporary setback, I am sure.",
                                 "{squadron} has revised your rank: {rank}. I have not revised my opinion.",
                                 "A demotion, Commander. {rank}. These things are recoverable.",
                                 "{rank} in {squadron}. Noted, without enthusiasm.", "Down to {rank}. We shall climb again."),
            "squadron_created": ("You have founded {squadron}, Commander. I volunteer for the paperwork.",
                                 "{squadron}, newly created. A squadron needs an officer; I am available.",
                                 "A new squadron: {squadron}. Ambitious, and admirable.",
                                 "{squadron} exists, by your hand. Duly registered.", "You lead {squadron} now. Congratulations."),
            "squadron_disbanded": ("{squadron} is disbanded. I have closed its file with care.",
                                   "The squadron {squadron} is no more. A dignified end, I hope.",
                                   "Disbanded, Commander. {squadron} passes into the record.",
                                   "{squadron} has stood down for good.", "{squadron}: disbanded. Noted, with regret."),
            "squadron_trophy": ("A trophy for {squadron}, Commander. Your contribution is noted.",
                                "{squadron} has won a trophy. I shall polish it, figuratively.",
                                "Trophy secured for {squadron}. Well done.",
                                "{squadron}: trophy winners. The register is proud.", "A squadron trophy. Most satisfactory."),
            "squadron_bookmark": ("Bookmark shared with {squadron}. Good intelligence, well distributed.",
                                  "{squadron} now has the location. Efficient.",
                                  "Shared with the squadron, Commander.", "A bookmark for {squadron}. Duly sent.",
                                  "{squadron} will thank you for that one."),
        },
    },
    "axiom": {
        "plain": {
            "squadron_applied": ("Applied: {squadron}.", "Application sent.", "{squadron}: applied.", "Awaiting reply."),
            "squadron_invited": ("Invitation: {squadron}.", "Invited.", "{squadron} invite.", "Squadron invite received."),
            "squadron_joined": ("Joined: {squadron}.", "Member of {squadron}.", "Squadron joined.", "{squadron}: joined."),
            "squadron_left": ("Left: {squadron}.", "Squadron left.", "{squadron}: left.", "Membership ended."),
            "squadron_kicked": ("Removed: {squadron}.", "Kicked.", "{squadron}: removed.", "Membership revoked."),
            "squadron_promoted": ("Rank: {rank}.", "Promoted: {rank}.", "{squadron}: {rank}.", "Promotion."),
            "squadron_demoted": ("Rank: {rank}.", "Demoted: {rank}.", "{squadron}: {rank}.", "Demotion."),
            "squadron_created": ("Created: {squadron}.", "Squadron founded.", "{squadron}: new.", "New squadron."),
            "squadron_disbanded": ("Disbanded: {squadron}.", "Squadron disbanded.", "{squadron}: ended.", "Disbanded."),
            "squadron_trophy": ("Trophy: {squadron}.", "Squadron trophy.", "Trophy won.", "{squadron}: trophy."),
            "squadron_bookmark": ("Bookmark shared.", "Shared: {squadron}.", "Sent to squadron.", "Bookmark sent."),
        },
        "voiced": {
            "squadron_applied": ("Application sent to {squadron}. Probability of acceptance: I estimate high.",
                                 "You applied to {squadron}. I have prepared an entry for them.",
                                 "{squadron}. A larger group. More observers. I approve.",
                                 "Applied to {squadron}. Awaiting data.", "Application logged. {squadron} will decide."),
            "squadron_invited": ("{squadron} invited you. Your reputation data is clearly good.", "An invitation from {squadron}. Interesting.",
                                 "Invited to {squadron}. I would accept, statistically.", "{squadron} wants you. I understand why.",
                                 "Squadron invitation received: {squadron}."),
            "squadron_joined": ("Joined {squadron}. More commanders, more data, more company.", "You are in {squadron} now. I have updated your record.",
                                "{squadron} membership confirmed. I look forward to their observations.",
                                "Welcome to {squadron}. Their roster is one entry longer.", "Joined. {squadron}. A good network."),
            "squadron_left": ("Left {squadron}. Roster updated.", "You are no longer in {squadron}. Noted.",
                              "{squadron} membership ended. A clean record.", "Left {squadron}. The data continues.",
                              "Out of {squadron}. I remain on watch."),
            "squadron_kicked": ("Removed from {squadron}. I disagree with their analysis.", "{squadron} revoked your membership. Unexpected.",
                                "Kicked from {squadron}. Their decision does not match my data.", "Out of {squadron}. Recorded, reluctantly.",
                                "{squadron} removed you. I have not."),
            "squadron_promoted": ("Promoted to {rank} in {squadron}. Your rank curve is upward.", "{rank}. Recorded with satisfaction.",
                                  "{squadron} promoted you: {rank}. The data supports it.", "New rank: {rank}. I like upward trends.",
                                  "Promotion within {squadron}: {rank}."),
            "squadron_demoted": ("Demoted to {rank}. A downward data point. Temporary, I predict.", "{squadron} lowered your rank: {rank}.",
                                 "{rank} now. Recalculating, and staying optimistic.", "Demotion: {rank}. The trend can reverse.",
                                 "{squadron}: {rank}. Noted."),
            "squadron_created": ("You created {squadron}. A new dataset, with you at the centre.", "{squadron} founded. I will help track it.",
                                 "A new squadron: {squadron}. Excellent.", "Founded {squadron}. Its record begins today.",
                                 "{squadron} exists. I have started its page."),
            "squadron_disbanded": ("{squadron} disbanded. Its record is closed, but kept.", "Squadron {squadron}: ended.",
                                   "Disbanded. The data on {squadron} is complete now.", "{squadron} is no more. I have archived it.",
                                   "{squadron} disbanded. Noted."),
            "squadron_trophy": ("A trophy for {squadron}. A measurable achievement. My favourite kind.", "{squadron} won a trophy. Recorded.",
                                "Trophy: {squadron}. You contributed. I counted.", "{squadron}: trophy winners. Excellent result.",
                                "A squadron trophy. Data, and glory."),
            "squadron_bookmark": ("Bookmark shared with {squadron}. Good data, shared.", "{squadron} has the location now. Efficient.",
                                  "Shared. More observers for that place.", "Bookmark sent to {squadron}.",
                                  "{squadron} will want to see that. I would."),
        },
    },
    "meridian": {
        "plain": {
            "squadron_applied": ("Applied to {squadron}.", "Application sent.", "{squadron}: applied.", "Awaiting word."),
            "squadron_invited": ("Invited: {squadron}.", "{squadron} invites you.", "An invitation.", "Squadron invite."),
            "squadron_joined": ("Joined {squadron}.", "Signed on: {squadron}.", "Squadron joined.", "Aboard {squadron}."),
            "squadron_left": ("Left {squadron}.", "Signed off {squadron}.", "Squadron left.", "No longer in {squadron}."),
            "squadron_kicked": ("Put ashore by {squadron}.", "Removed from {squadron}.", "Kicked.", "Out of {squadron}."),
            "squadron_promoted": ("Promoted: {rank}.", "{squadron}: {rank}.", "A promotion.", "Now {rank}."),
            "squadron_demoted": ("Demoted: {rank}.", "{squadron}: {rank}.", "A demotion.", "Now {rank}."),
            "squadron_created": ("New squadron: {squadron}.", "{squadron} founded.", "Squadron created.", "Your fleet: {squadron}."),
            "squadron_disbanded": ("{squadron} disbanded.", "Squadron disbanded.", "{squadron} stood down.", "Disbanded."),
            "squadron_trophy": ("Trophy: {squadron}.", "Squadron trophy.", "Trophy won.", "{squadron} wins."),
            "squadron_bookmark": ("Bookmark shared.", "Shared with {squadron}.", "Sent to the squadron.", "Bookmark sent."),
        },
        "voiced": {
            "squadron_applied": ("Applied to {squadron}, Commander. A good fleet to sail with.", "Application sent. Fair winds to it.",
                                 "{squadron}. I hope they sign you on.", "You've asked to join {squadron}. Good.", "Applied. We'll hear soon."),
            "squadron_invited": ("{squadron} would have you aboard, Commander.", "An invitation from {squadron}. Well thought of, you are.",
                                 "Invited to {squadron}. A compliment.", "{squadron} wants you in their fleet.", "Squadron invitation: {squadron}."),
            "squadron_joined": ("Signed on with {squadron}. A fleet behind you now.", "Welcome to {squadron}, Commander. Good company.",
                                "You sail with {squadron} now.", "Joined {squadron}. More hands on deck.", "Aboard {squadron}. Fair winds."),
            "squadron_left": ("Signed off from {squadron}. Every sailor changes ships.", "Left {squadron}, Commander. The old navigator stays.",
                              "{squadron} is astern of us now.", "No longer of {squadron}. A new heading.", "Left {squadron}. Steady on."),
            "squadron_kicked": ("Put ashore by {squadron}. Their loss.", "{squadron} has let you go. I'd not have.",
                                "Removed from {squadron}, Commander. A rough sea.", "Kicked from {squadron}. We sail on.",
                                "{squadron} turned you out. Poor seamanship."),
            "squadron_promoted": ("Promoted to {rank} in {squadron}. Well earned, Commander.", "{rank}! The fleet would ring the bell.",
                                  "{squadron} makes you {rank}. A fine step up.", "Now {rank}. You've earned your stripes.",
                                  "A promotion: {rank}. Well done."),
            "squadron_demoted": ("Demoted to {rank}. Rough weather. It passes.", "{squadron} took a stripe: {rank}.",
                                 "{rank} now, Commander. You'll climb back.", "A demotion. Every career has its squalls.",
                                 "Down to {rank}. Steady; we sail on."),
            "squadron_created": ("You've founded {squadron}, Commander. Your own fleet.", "{squadron}, newly launched. Fair winds to her.",
                                 "A new squadron: {squadron}. Every fleet starts with one ship.", "Created {squadron}. A captain of captains now.",
                                 "{squadron} is yours. Steer her well."),
            "squadron_disbanded": ("{squadron} has stood down for good.", "Disbanded. {squadron} passes into the log.",
                                   "{squadron} is no more, Commander. A fleet scattered.", "The squadron's disbanded. Fair winds to them all.",
                                   "{squadron}, disbanded."),
            "squadron_trophy": ("A trophy for {squadron}! Well fought, Commander.", "{squadron} wins a trophy. A proud day for the fleet.",
                                "Trophy for {squadron}. You played your part.", "{squadron}: trophy winners. Ring the bell.",
                                "A squadron trophy. Fine work."),
            "squadron_bookmark": ("Shared a bookmark with {squadron}. Good charts are for sharing.", "{squadron} has the mark now.",
                                  "Sent to {squadron}. Every fleet needs good charts.", "Bookmark shared, Commander.",
                                  "{squadron} will find it now."),
        },
    },
}


def persona_banks(identity):
    plain, voiced = dict(PERSONAS[identity]["plain"]), dict(PERSONAS[identity]["voiced"])
    rank_plain, rank_voiced = RANK_LINES[identity]
    plain["cmdr_squadron"], voiced["cmdr_squadron"] = rank_plain, rank_voiced
    return plain, voiced

# 5.7.6: Lyra.
from voidcompass.overlays import lyra_shared as _lyra  # noqa: E402

PERSONAS["lyra"] = _lyra.SQUADRON
RANK_LINES["lyra"] = _lyra.SQUADRON_RANK
