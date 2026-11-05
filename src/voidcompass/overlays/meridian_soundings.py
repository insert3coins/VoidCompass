"""Meridian's navigation voice (5.7.4): it is the navigator, so jumps, distance
and the long cruise matter more to it than to the rest of the crew, and it has
enough to say that a long run of jumps doesn't wear thin."""

# Topics it rates above the shared importance: on Occasional it notes an
# arrival or a long stride; on Rare it still marks a new position now and then.
INTERESTS = {
    "arrival": 2, "jump_long": 2, "jump_far": 2, "carrier_jump": 2, "idle_supercruise": 2, "idle_far": 2,
    "scooped": 1, "fss_complete": 1,
}

PLAIN = {
    "arrival": ("Position: {system}.", "{system}. Course holding.", "In {system}. Class {star}.",
                "{system}. Position fixed."),
    "jump_long": ("{dist} made good.", "Jump: {dist}.", "{dist}. Course holding.", "{dist} logged."),
    "jump_far": ("Long distance made good.", "We are well out now.", "A great distance behind us.",
                 "Far from the start of this voyage."),
    "scooped": ("Fuel aboard.", "Tanks full.", "Refuelled. Course clear."),
    "carrier_jump": ("Carrier at {system}.", "Carrier position: {system}.", "The carrier is in {system}.",
                     "Carrier jump logged: {system}."),
    "idle_supercruise": ("Under way in {system}.", "{system}. Steady in supercruise.", "Cruising. All quiet.",
                         "{system}. Holding course."),
    "idle_far": ("Position: {dist} from Sol.", "{dist} out from Sol.", "{dist} from Sol. Steady.",
                 "Range from Sol: {dist}."),
    "fss_complete": ("{system} charted.", "Chart complete: {system}.", "{system}: all bodies on the chart."),
}

VOICED = {
    "arrival": ("{system}. Position fixed and entered in the log.",
                "Arrived at {system}. Class {star} primary. Fair skies.",
                "{system}. A new name on the chart, and the course still true.",
                "{system}, Commander. Another stride made good.",
                "In {system}. Mark the time; this is where we were.",
                "{system}. The primary is {star}. I have seen worse harbours.",
                "Landfall of a sort: {system}. Steady as she goes.",
                "{system}. The log grows a line longer. As it should."),
    "jump_long": ("{dist} in one stride. The old fleet would have taken a week.",
                  "A {dist} jump. Cleanly done, Commander.",
                  "{dist}. That is a fine piece of ship handling.",
                  "{dist} made good. I like a jump that leaves the stars properly rearranged.",
                  "{dist}. The chart turns another page.",
                  "Long jump: {dist}. The drive earned its keep there."),
    "jump_far": ("We are a long way out now. I have marked the way home, as I always do.",
                 "The distance behind us is considerable. So is the distance ahead. Good.",
                 "A long voyage, Commander. The log is thick with it.",
                 "Further than most go. Keep a good margin and we will go further still."),
    "scooped": ("Tanks full. A navigator sleeps better with a full tank.",
                "Fuel aboard. The next leg is ours to choose.",
                "Scooped and ready. Every friendly star is a harbour.",
                "Refuelled. Margin restored. Carry on."),
    "carrier_jump": ("The carrier has made {system}. A whole harbour, moved again.",
                     "{system}. The carrier jumped and arrived. The old ships never managed that.",
                     "Carrier in {system}. I have moved the anchor on my chart.",
                     "{system}. The carrier holds station. Good seamanship, after a fashion."),
    "idle_supercruise": ("Supercruise in {system}. The quiet watches are my favourite.",
                         "{system}. Plenty of room and nothing in the way. Fine sailing.",
                         "Under way through {system}. I could do this for a very long time.",
                         "Cruising in {system}. The instruments are calm, and so am I.",
                         "{system}. A long cruise is a navigator's rest."),
    "idle_far": ("{dist} from Sol. A long way from any harbour, and we are well found.",
                 "{dist} out. I keep the bearing home in the back of my mind. Always.",
                 "{dist} from Sol, Commander. There is no shame in being proud of that.",
                 "{dist}. The old charts stop well before this. Ours do not."),
    "fss_complete": ("{system} fully charted. A navigator's dream: no surprises left from orbit.",
                     "Every body in {system} on the chart. Well surveyed.",
                     "{system}: charted. If we come back, we will know her."),
}
