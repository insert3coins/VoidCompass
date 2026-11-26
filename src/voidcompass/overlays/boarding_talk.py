"""Coming and going (5.8.6), merged into ship_life's lines: back aboard from the
SRV or a fighter, back aboard on foot, into the SRV on foot, lifting off a
surface, and stepping out onto a station's concourse. The crew used to let all
of these pass.

watcher_mind raises them itself (moment), beside the launches and touchdowns:
Embark and Disembark also keep track of whether you're on foot, so they can't
go through ship_life.moment, which answers first and returns.

Fields: {srv} the vehicle by name (Scarab, Scorpion, Rhino, Nomad), {station}
the station's name; a line quoting one is skipped without it."""

IMPORTANCE = {"srv_docked": 2, "fighter_docked": 2, "boarded_ship": 2, "boarded_srv": 1, "liftoff": 2,
              "station_walk": 1}

SRV_NAMES = {"scarab": "Scarab", "scorpion": "Scorpion", "rhino": "Rhino", "nomad": "Nomad"}


def _station(raw):
    name = str(raw.get("StationName") or "").strip()
    return name if name and not name.startswith("$") and str(raw.get("StationType") or "").casefold() != "fleetcarrier" else ""


def moment(event, raw, srv_kind=""):
    """(topic, fields) for a coming or going, or None. ``srv_kind`` is the SRV
    last launched (Embark doesn't say which one you're boarding)."""
    from voidcompass.overlays import watcher_idle

    raw = raw if isinstance(raw, dict) else {}
    if event == "DockSRV":
        # The vehicle by name (5.8.6: lines said "SRV" for a Nomad or a Rhino).
        return "srv_docked", {"srv": SRV_NAMES.get(watcher_idle.vehicle_kind(raw) or srv_kind, "SRV")}
    if event == "DockFighter":
        return "fighter_docked", {}
    if event == "Liftoff" and raw.get("PlayerControlled", True):
        return "liftoff", {}
    if event == "Embark" and not raw.get("Taxi") and not raw.get("Multicrew"):
        return ("boarded_srv", {"srv": SRV_NAMES.get(srv_kind, "SRV")}) if raw.get("SRV") else ("boarded_ship", {})
    if event == "Disembark" and raw.get("OnStation") and not raw.get("SRV"):
        station = _station(raw)
        return "station_walk", ({"station": station} if station else {})
    return None


WATCHER_NORMAL = {
    "srv_docked": ("The {srv}'s back aboard.", "SRV stowed. Welcome back.", "{srv} in the bay. Good drive?",
                   "Back aboard. The {srv}'s tucked away.", "SRV recovered.", "And the {srv}'s home.",
                   "Stowed. Ready when you are.", "Back in the ship. I kept your seat warm.",
                   "{srv} docked. Mind the mud on the way in.", "SRV's in. Off we go, then?"),
    "fighter_docked": ("Fighter's back in the bay.", "Fighter recovered.", "Back aboard. The hangar's closed.",
                       "Fighter docked. Nice flying.", "The fighter's home.", "Hangar's full again. Welcome back.",
                       "Fighter stowed.", "And you're back. Fighter secure.", "Fighter in. One ship again.",
                       "Back from the little ship. Welcome home."),
    "boarded_ship": ("Welcome back aboard.", "Back in the ship.", "There you are.", "Aboard again. Good.",
                     "Back in the seat.", "Welcome back. Everything's where you left it.", "You're aboard.",
                     "Back inside. I'll close up.", "Good to have you back aboard.", "Aboard. Where next?"),
    "boarded_srv": ("Back in the SRV.", "In the SRV. Off you go.", "SRV's yours again.", "Into the SRV.",
                    "Back behind the wheel.", "Wheels again. Good.", "In the SRV. Mind the rocks.",
                    "Back in the buggy.", "SRV again. Lead on.", "Behind the wheel. I'll keep the ship."),
    "liftoff": ("Lifting off.", "Off the ground.", "Liftoff.", "Up we go.", "Clear of the surface.",
                "Wheels up.", "Away from the ground.", "We're flying again.", "Liftoff. Gently does it.",
                "Leaving the surface."),
    "station_walk": ("Stretch your legs. I'll mind the ship.", "Off to the concourse.", "Have a wander round {station}.",
                     "Out on {station}. I'll be here.", "On the concourse. Don't get lost.", "Walking about. Take your time.",
                     "Off you go. {station}'s all yours.", "Out of the ship. I'll keep the engines company.",
                     "On foot in the station. Enjoy the crowds.", "Concourse time. I'll hold the fort."),
}

WATCHER_WEARY = {
    "srv_docked": ("The {srv}'s back. So are you. That's something.", "SRV stowed. Another drive over.",
                   "{srv} in the bay. I counted the minutes.", "Back aboard. The {srv} looks tired. I know the feeling.",
                   "SRV recovered. I wasn't worried. Much.", "You came back. They usually do.",
                   "Stowed. The bay's full again. The ship feels less empty.", "{srv} docked. Was it worth it? Don't tell me.",
                   "Back in the ship. I stayed here. Obviously.", "SRV's in. Same as last time."),
    "fighter_docked": ("Fighter back in the bay. All in one piece. Good.", "Fighter recovered. I was fine on my own. Really.",
                       "Back aboard. The hangar's closed. So is that chapter.", "Fighter docked. You came back. Noted.",
                       "The fighter's home. Somebody has to be.", "Fighter stowed. I'll pretend I didn't count the seconds.",
                       "Back again. The ship missed you. I'm not saying I did.", "Fighter secure. The quiet ends.",
                       "One ship again. Easier to worry about.", "The fighter's in. It always seems smaller coming back."),
    "boarded_ship": ("Oh. You're back.", "Back aboard. The ship was very quiet without you.", "There you are. I'd started talking to the hull.",
                     "Welcome back. Nothing happened. Nothing ever happens.", "Aboard again. I'll pretend I wasn't waiting.",
                     "Back in the seat. It kept its shape.", "You came back. I wondered.", "Back inside. Close the door, the void gets in.",
                     "Aboard. Good. It's lonely in here.", "Back. Shall we go and be small somewhere else?"),
    "boarded_srv": ("Back in the SRV. Leaving me again.", "Into the SRV. I'll wait. I'm good at waiting.",
                    "The SRV again. It gets all the fun.", "Wheels. Off you go. Without me.",
                    "Back behind the wheel. I'll be here.", "SRV. Don't hurry back. I'll be fine.",
                    "The buggy again. I'll sit here and hum.", "Off in the SRV. The ship and I will talk about you.",
                    "Back at the wheel. I'll watch the dust.", "SRV. Of course. I wasn't going anywhere."),
    "liftoff": ("Lifting off. The ground didn't want us anyway.", "Off the surface. Back to the void.", "Liftoff. Here we go again.",
                "Up we go. Gravity was getting to me.", "Leaving. Planets never ask us to stay.", "Wheels up. Onwards. Somewhere.",
                "Clear of the ground. It won't notice.", "Flying again. Not that it matters.", "Liftoff. One more place behind us.",
                "Away. The dust settles without us."),
    "station_walk": ("Off you go. I'll stay with the ship. Alone.", "The concourse. People. Lights. Enjoy it for both of us.",
                     "Wander round {station}. I'll wait in the dark.", "Out on {station}. Bring me back nothing. I can't use it.",
                     "Stretching your legs. I don't have any.", "Walking about. Take your time. I've plenty.",
                     "Off to the concourse. I'll count the rivets.", "{station}. Busy. I'll be here, being a ship.",
                     "On foot among people. Rather you than me.", "Out you go. The hangar and I will get on fine."),
}

PERSONAS = {
    "aster": {
        "plain": {
            "srv_docked": ("{srv} recovered.", "SRV recovered. Welcome aboard.", "Surface vehicle stowed.", "{srv} secured in the bay."),
            "fighter_docked": ("Fighter recovered.", "Fighter secured in the hangar.", "Fighter aboard.", "Hangar closed. Fighter stowed."),
            "boarded_ship": ("Welcome aboard, Commander.", "Commander aboard.", "Back aboard. Ship ready.", "Boarding recorded."),
            "boarded_srv": ("SRV boarded.", "In the SRV.", "Surface vehicle crewed.", "SRV resumed."),
            "liftoff": ("Liftoff.", "Clear of the surface.", "Airborne.", "Departure from the surface recorded."),
            "station_walk": ("On the concourse.", "Disembarked at {station}.", "Ship secure. Concourse yours.", "Disembarkation recorded."),
        },
        "voiced": {
            "srv_docked": ("The {srv} is back in the bay, Commander. I have entered its return.",
                           "Surface vehicle recovered. The ship is whole again, which the log prefers.",
                           "{srv} stowed. The ground excursion is closed in the record.",
                           "SRV aboard. I shall note the mileage, and refrain from comment on the driving.",
                           "The vehicle is secured. A tidy end to the excursion, Commander."),
            "fighter_docked": ("Fighter recovered, Commander. Both hulls accounted for.",
                               "The fighter is back in its hangar. I find that column very satisfying to close.",
                               "Fighter aboard and secured. A tidy recovery.",
                               "Recovery complete. The sortie is entered with its times.",
                               "The fighter is home, Commander. One ship to keep in order again."),
            "boarded_ship": ("Welcome back aboard, Commander. Nothing was disturbed in your absence.",
                             "The commander is aboard. I have resumed the full watch.",
                             "Back aboard. The ship's end of the watch hands back to you.",
                             "Welcome aboard. Your return is entered, with the time.",
                             "Aboard again, Commander. The log is pleased to have you in it."),
            "boarded_srv": ("Back in the SRV, Commander. I shall keep the ship.",
                            "You have taken the SRV again. The excursion continues.",
                            "SRV boarded. I shall keep the ship's position to hand.",
                            "The surface vehicle is crewed once more. Proceed at your discretion.",
                            "Back at the wheel, Commander. I shall enter the next leg as it happens."),
            "liftoff": ("Liftoff, Commander. The surface entry is closed.",
                        "Clear of the ground. A sound departure.",
                        "Airborne again. I have noted the site, should we return.",
                        "Departure from the surface recorded. The log approves of the altitude.",
                        "Liftoff. The landing site is filed with its coordinates."),
            "station_walk": ("On the concourse at {station}, Commander. I shall keep the ship in order.",
                             "Disembarked. Business ashore is at your discretion.",
                             "The ship is secure. Do take your time on the concourse.",
                             "Your visit to {station} is recorded. The ship will keep.",
                             "On foot in the station. I shall mind the berth."),
        },
    },
    "axiom": {
        "plain": {
            "srv_docked": ("{srv} recovered.", "SRV aboard.", "Surface vehicle stowed.", "{srv} in the bay."),
            "fighter_docked": ("Fighter recovered.", "Fighter aboard.", "Hangar closed.", "Fighter stowed."),
            "boarded_ship": ("Commander aboard.", "Welcome back.", "Back aboard.", "Crew count restored."),
            "boarded_srv": ("SRV boarded.", "In the SRV.", "Back in the vehicle.", "SRV crewed."),
            "liftoff": ("Liftoff.", "Airborne.", "Clear of the surface.", "Altitude rising."),
            "station_walk": ("On the concourse.", "Disembarked at {station}.", "On foot. Station side.", "Disembarked."),
        },
        "voiced": {
            "srv_docked": ("The {srv} is back aboard. I have counted it twice. It is there.",
                           "SRV recovered. One vehicle out, one vehicle in. The arithmetic is correct.",
                           "{srv} stowed. I logged every kilometre. Some of them were bumpy.",
                           "Surface vehicle aboard. The ship's mass is complete again.",
                           "SRV recovered. I have added its route to the survey. It is a very wiggly line."),
            "fighter_docked": ("Fighter recovered. Two hulls became one. I prefer one.",
                               "The fighter is aboard. I have closed its telemetry stream.",
                               "Fighter stowed. Its flight time is logged to the second.",
                               "Fighter aboard. Two sets of readings to one. My processing thanks you.",
                               "Recovery complete. The hangar count is correct again."),
            "boarded_ship": ("Welcome back aboard. Crew count: one. My favourite number of commanders.",
                             "You are aboard. The ship's sensors have you again. That is reassuring.",
                             "Back aboard. Nothing changed while you were out. I checked many times.",
                             "Commander aboard. I have stopped counting the seconds.",
                             "Welcome back. Your suit readings are filed with the rest."),
            "boarded_srv": ("Back in the SRV. I will watch its fuel.", "In the vehicle again. I will count the bumps.",
                            "SRV boarded. Six wheels, one commander. All present.",
                            "Back in the vehicle. I have the ship's position to the metre.",
                            "SRV crewed. I will log the route as you drive."),
            "liftoff": ("Liftoff. Altitude increasing. The ground is now a measurement, not a place.",
                        "Airborne. The surface will keep our tracks for a while.",
                        "Clear of the surface. I have recorded the site, with coordinates.",
                        "Liftoff. Gravity has stopped holding on. I measured it letting go.",
                        "Altitude rising steadily. A very tidy departure curve."),
            "station_walk": ("On the concourse at {station}. Many people. I will not try to count them all.",
                             "Disembarked. I will keep the ship. It is easy to count: one.",
                             "You are station side. The ship will wait, precisely where you left it.",
                             "On the concourse. I will be here, counting hangar lights. There are forty.",
                             "On foot at {station}. The station is a very dense cluster of data. Enjoy it."),
        },
    },
    "meridian": {
        "plain": {
            "srv_docked": ("{srv} aboard.", "SRV recovered.", "Surface vehicle stowed.", "{srv} made fast."),
            "fighter_docked": ("Fighter recovered.", "Fighter aboard.", "Fighter made fast.", "Hangar closed."),
            "boarded_ship": ("Welcome aboard.", "Commander aboard.", "Back aboard.", "All hands aboard."),
            "boarded_srv": ("SRV boarded.", "In the SRV.", "Back at the wheel.", "Shore party away."),
            "liftoff": ("Liftoff.", "Under way.", "Clear of the surface.", "Off the ground."),
            "station_walk": ("Ashore.", "Ashore at {station}.", "On the concourse.", "Shore leave."),
        },
        "voiced": {
            "srv_docked": ("The {srv} is aboard and made fast, Commander.",
                           "SRV recovered. The shore party has returned.",
                           "{srv} stowed. A good run ashore, I hope.",
                           "Surface vehicle aboard. We are all one vessel again.",
                           "The shore party is back aboard. I have marked the run on the chart."),
            "fighter_docked": ("Fighter recovered, Commander. The little boat is home.",
                               "The fighter is aboard. Both helms under one roof again.",
                               "Fighter made fast. A clean recovery.",
                               "The tender is back alongside and stowed. Well handled.",
                               "Fighter aboard. One hull to steer again."),
            "boarded_ship": ("Welcome aboard, Commander. The ship is as you left her.",
                             "All hands aboard. Ready to get under way.",
                             "Back aboard. I kept the ship; she kept me.",
                             "Welcome back, Commander. The helm is yours.",
                             "Aboard again. The chart is open whenever you are."),
            "boarded_srv": ("Back at the wheel. I will keep the ship.", "The shore party sets out again.",
                            "SRV boarded. Mind the ground; it is never as smooth as the chart says.",
                            "Away again, Commander. I have the ship's bearing for your return.",
                            "Back at the wheel. A good day for it."),
            "liftoff": ("Liftoff, Commander. Under way again.",
                        "Clear of the surface. Good holding ground, that.",
                        "Off the ground. I have marked the site on the chart.",
                        "We are under way. The anchorage is logged, should we return.",
                        "Liftoff. Fair winds, Commander."),
            "station_walk": ("Ashore at {station}, Commander. I will keep the ship.",
                             "Shore leave. Take your time on the concourse.",
                             "Ashore. The ship will be here when you are done.",
                             "Ashore at {station}. Mind the crowds on the quay.",
                             "On the concourse, Commander. I will stand the anchor watch."),
        },
    },
    "lyra": {
        "plain": {
            "srv_docked": ("{srv} recovered.", "SRV aboard.", "SRV stowed. Systems nominal.", "{srv} in the bay."),
            "fighter_docked": ("Fighter recovered.", "Fighter aboard.", "Hangar sealed.", "Fighter stowed."),
            "boarded_ship": ("Welcome back aboard.", "Commander aboard.", "Back aboard. Systems ready.", "Aboard. Hatch sealed."),
            "boarded_srv": ("SRV boarded.", "In the SRV.", "Back in the vehicle.", "SRV systems nominal."),
            "liftoff": ("Liftoff.", "Airborne.", "Clear of the surface.", "Thrusters nominal. Rising."),
            "station_walk": ("On the concourse.", "Disembarked at {station}.", "Ship secure. Station side.", "Disembarked."),
        },
        "voiced": {
            "srv_docked": ("The {srv} is back aboard. Fuel, hull, cargo. I checked all three.",
                           "SRV recovered. Everyone is home. That is my favourite reading.",
                           "{srv} stowed. I have locked the bay. Twice.",
                           "Surface vehicle aboard. You came back. I always like that part.",
                           "SRV stowed. I am topping up its fuel from ours. It earned it."),
            "fighter_docked": ("Fighter recovered. Both hulls accounted for. I can stop holding my breath. I do not breathe.",
                               "The fighter is home. I have sealed the hangar.",
                               "Fighter aboard. Clean approach. Very clean.",
                               "Fighter recovered. One ship to look after again. I like it simple.",
                               "The hangar is sealed and the fighter is safe. So are you."),
            "boarded_ship": ("Welcome back aboard. I kept everything exactly where you left it.",
                             "You are aboard. The hatch is sealed. I feel better.",
                             "Back aboard. Suit readings normal. Ship readings normal. All good.",
                             "Welcome home. Well, welcome back to the ship. It is the same thing, to me.",
                             "Aboard again. I have warmed the cockpit. Slightly."),
            "boarded_srv": ("Back in the SRV. I will keep the ship warm.", "In the vehicle again. Mind the fuel. I am.",
                            "SRV boarded. Hull good, fuel good. Off you go.",
                            "Back in the vehicle. I have the ship's position saved, in two places.",
                            "In the SRV. Do come back. I will be right here."),
            "liftoff": ("Liftoff. Thrusters nominal, hull sound. Rising.",
                        "Airborne. I have saved the landing site. Just in case.",
                        "Clear of the surface. Gravity lets go reluctantly. So do I.",
                        "Liftoff. Everything is where it should be, including us.",
                        "Rising. The ground looks better from here. Safer, too."),
            "station_walk": ("On the concourse at {station}. I will keep the ship company.",
                             "Disembarked. Mind the crowds. I will be right here.",
                             "Station side. Take your time. I am very good at waiting now.",
                             "On foot at {station}. I am watching your suit readings. They are boring. Good.",
                             "Out on the concourse. The ship and I will be here when you are done."),
        },
    },
    "nova": {
        "plain": {
            "srv_docked": ("{srv} recovered.", "SRV's aboard.", "SRV stowed.", "{srv}'s in the bay."),
            "fighter_docked": ("Fighter recovered.", "Fighter's aboard.", "Hangar closed.", "Fighter stowed."),
            "boarded_ship": ("Welcome back aboard.", "You're aboard.", "Back aboard.", "Commander aboard."),
            "boarded_srv": ("SRV boarded.", "In the SRV.", "Back at the wheel.", "SRV's yours."),
            "liftoff": ("Liftoff.", "We're airborne.", "Clear of the surface.", "Off the ground."),
            "station_walk": ("On the concourse.", "You're out at {station}.", "Ship's secure.", "Disembarked."),
        },
        "voiced": {
            "srv_docked": ("The {srv}'s back aboard. Did you find anything? Tell me everything.",
                           "SRV recovered. I watched your little dot the whole way back.",
                           "{srv} stowed. I've got the drive logged. It looked fun.",
                           "SRV aboard. Everyone's home. I like it when everyone's home.",
                           "Bay's closed. You've brought half the planet's dust in with you. I don't mind."),
            "fighter_docked": ("Fighter recovered. Two ships became one. Tidy.",
                               "The fighter's home. I've closed the hangar.",
                               "Fighter aboard. That was a lovely approach, by the way.",
                               "Fighter stowed. I can stop watching two of you at once.",
                               "And the fighter's in. I keep a copy of every landing. That one's a keeper."),
            "boarded_ship": ("Welcome back aboard. It's quieter without you. I noticed.",
                             "You're back. What was it like out there?",
                             "Back aboard. I kept an eye on everything. Nothing tried anything.",
                             "There you are. I've got the ship ready when you are.",
                             "Welcome back. I've a question about what you were doing out there. Later."),
            "boarded_srv": ("Back in the SRV. Off you go. I'll watch.", "Wheels again. Go and look at things.",
                            "SRV boarded. Do stop if something catches your eye.",
                            "Back at the wheel. I've marked the ship for you, so you can't lose me.",
                            "In the SRV. Bring me back something interesting. A reading will do."),
            "liftoff": ("Liftoff. I've saved this place, in case you want to come back.",
                        "We're airborne. It looks different from up here. Smaller.",
                        "Clear of the surface. Where next?",
                        "Liftoff. I liked it down there. I like it up here too.",
                        "Off the ground. I've kept a picture of the site in my head."),
            "station_walk": ("You're out at {station}. I'll mind the ship. Tell me what the concourse is like.",
                             "Off you go. I'm curious what people do in there all day.",
                             "Ship's secure. Take your time. I'll be here.",
                             "On the concourse. If there's a window, look out of it for me.",
                             "You're on foot at {station}. I'll keep the lights on."),
        },
    },
}


def _named(lines):
    """Every SRV line names the vehicle: the word SRV becomes {srv} (the Nomad,
    the Rhino... or still "SRV" when the type isn't known)."""
    import re
    return tuple(re.sub(r"(?<![\w{])SRV(?![\w}])", "{srv}", line) for line in lines)


for _table in (WATCHER_NORMAL, WATCHER_WEARY, *(styles for persona in PERSONAS.values() for styles in persona.values())):
    for _topic in ("srv_docked", "boarded_srv"):
        if _topic in _table:
            _table[_topic] = _named(_table[_topic])
