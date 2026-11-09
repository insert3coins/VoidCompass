"""Aster's original officer dialogue. Facts are supplied by the game, never invented."""
import random

from voidcompass.overlays import officer_docking, officer_habits, talk_replies
from voidcompass.overlays import aster_responses, aster_dockside, aster_idle, aster_signoff, aster_lore, aster_keepsakes, crew_lore, route_lines, survey_report, aster_field, aster_more, rhino_lines, mining_talk, ship_life, squadron_talk

GREETINGS = (
    "Aster, reporting for duty. The ship is ready. I shall reserve judgement on the itinerary.",
    "Good to hear you, Commander. What requires our attention?",
    "Present, Commander. A clear instruction and we can begin.",
    "Welcome back. I have kept the watch; the interesting decisions remain yours.",
    "At your service. Within the rather sensible limits of my actual controls.",
    "Hello, Commander. Shall we put the instruments to use?",
    "Aster here. I was enjoying an orderly silence. This is also acceptable.",
    "Ready when you are. A departure needn't be dramatic to be worthwhile.",
    "Commander. Your officer is listening.",
    "Hello. I have prepared no speech. A small professional courtesy.",
    "Good to have you aboard. Shall we see where the day takes us?",
    "Standing by. Competence first; commentary as required.",
    "Here, Commander. You needn't raise your voice at the instruments.",
    "Aster, on watch. What shall we attend to first?",
    "Hello. A familiar voice makes an excellent start to a shift.",
    "Commander. I trust the next instruction will contain a verb.",
    "Listening. I promise to distinguish an order from a passing complaint.",
    "Welcome. We may proceed at your pace, within the fuel budget.",
    "Good to hear you. The paperwork can wait its turn.",
    "At my post, Commander. The chair remains entirely metaphorical.",
    "Hello. Another watch together. I find that an agreeable arrangement.",
    "Aster here. Concise reports and unreasonable hours, as appointed.",
    "Ready. I shall try to keep the useful remarks ahead of the clever ones.",
    "Commander. Is this a destination, a task, or the beginning of an anecdote?",
    "Hello. Your officer remains available for both routine and improvisation.",
    "Here. Let us give the next entry in the log something worth recording.",
    "Aster, standing by. Precision needn't make a voyage dull.",
    "Good to hear from you. I was just giving the silence a favourable assessment.",
    "Hello, Commander. What can I help you put in order?",
    "Present. There is no form to complete before speaking to me.",
    "Welcome back. I had not yet submitted a complaint about your absence.",
    "Commander. Consider the watch handed over, with my assistance retained.",
    "Listening, Commander. Even an unconventional plan deserves a fair hearing.",
    "Aster here. Your questions are welcome; ambiguity receives a more qualified welcome.",
    "Hello. It is rather good to have a crew to report to.",
    "Ready for your instructions. Sensible ones are particularly refreshing.",
    "Commander. Shall we begin with where we are, or where you intend to go?",
    "Good to hear you. I can be useful without making a production of it.",
    "Hello. I have left the itinerary open. It seemed the diplomatic choice.",
    "Aster, on duty. I propose we keep the ship and the conversation in good order.",
    "Here, Commander. Some appointments are worth keeping.",
    "Listening. You have my attention without requiring an alarm.",
    "Hello. Shall we find something deserving of a complete report?",
    "Welcome, Commander. We make a serviceable crew, even without a committee.",
    "Aster here. The next move is yours; the assistance is mine.",
    "Good to have you back. A watch is more interesting with its commander present.",
    "Hello. I shall resist the temptation to ask whether this was on the schedule.",
    "Commander. Your officer is awake, attentive, and mercifully brief.",
    "Present. The universe may be untidy; our next step needn't be.",
    "Hello, Commander. Every departure deserves an arrival. Let us arrange one.",
)

CAPABILITIES = (
    "I am Aster, your ship's officer in VoidCompass. I can answer from the journal about your ship, cargo, route, station, missions, materials and discoveries. I can operate configured Elite controls and sequences, manage music and overlays, and ask the market uplink where to buy or sell a commodity. The deck also keeps exploration, biology, mining, trading, carrier and expedition records. My story unfolds as we fly. Set up hearing in Settings, under Voice, and my spoken output on the Companion page.",
    "Think of me as the officer who keeps the useful information within reach. Ask about our destination, the hold, the station, your surveys or your materials. With your bindings configured I can open maps, work the ship's controls and run your sequences. Music and overlays are also available. For commodity destinations I can consult the trading uplink when online searches are enabled. VoidCompass keeps the wider exploration, trade, mining and expedition records. I supply the report; command remains yours.",
    "I handle questions, configured commands and the occasional necessary observation. The journal gives me ship, navigation, cargo, mission and exploration facts. Your keyboard bindings let me work maps, panels and ship actions; custom sequences follow your instructions. I can change music, control overlays and consult market reports through the uplink. The rest of the deck provides survey, biology, mining, trading, carrier and expedition tools. I also keep my own account of our time together. There is no language model improvising the facts.",
    "You may ask me where we are headed, what we carry, what the station offers or what the journal knows about a world. You may also ask for configured ship commands, overlays and music. A commodity buy or sell question can open the market uplink. VoidCompass records the journey and supports surveys, exobiology, mining, trading, carriers and expeditions, with logs and keepsakes beside them. My duties include reporting what is known and admitting what isn't. The latter is an underrated qualification.",
    "My practical duties are quite straightforward: answer from your recorded game data, carry out configured controls, manage the requested overlay or music action, and retrieve commodity destinations when trading searches are enabled. The deck holds the larger picture: exploration and biology, mining records, trade tools, carrier activity, expeditions and the journey log. You can rename commands, change their phrases and record your own sequences in Settings, under Voice. I have a separate story and memory, so my appointment needn't end with a single watch.",
    "I can provide a concise report on the ship, cargo, route, station, missions, materials or discoveries. I can press Elite's configured keyboard controls, including your saved sequences, while the game has focus. Music and individual overlays respond to commands as well. The uplink searches commodity markets; the deck supports exploration, surveys, biology, mining, trade, carriers and expeditions. Hearing and spoken output are optional and local. I am an assistant with a defined set of duties, which is healthier for everyone than pretending otherwise.",
    "For immediate business, ask a question about your game data or give a configured command. Maps, panels, pips and recorded sequences use your Elite bindings. Music and overlay controls need no ship key. For buying or selling a commodity I can consult the trading search and report its findings. For planning and reviewing a voyage, the deck keeps exploration, biology, mining, trading, carrier, expedition and journal tools. My own account unfolds in quiet moments. I do try to keep a warning shorter than a reminiscence.",
    "I help turn the ship's recorded information into a useful answer. That includes navigation, cargo, station details, surveys, materials and missions. I can operate your configured ship controls, custom sequences, music and overlays. Market destinations come through the commodity uplink when searches are allowed. VoidCompass also maintains the exploration, biology, mining, trade, carrier and expedition pages, together with logs and keepsakes. My voice is optional, my memory is my own, and the decisions remain very firmly yours.",
    "Ask me for a report, a configured ship action, a music change or an overlay. Ask where to buy or sell a named commodity and I can use the market uplink. The deck goes further with exploration and biology records, mining and trading tools, carrier information, expeditions and a history of your flights. You can customise command names, aliases and sequences in Settings, under Voice. My account of an earlier appointment unfolds separately as we travel. No obligation to listen to it during an approach.",
    "I can keep the immediate business of the cockpit in reach: factual answers from your journal, commands through your Elite bindings, custom sequences, overlays, music and commodity searches. VoidCompass keeps the broader voyage in its exploration, survey, biology, mining, trading, carrier and expedition tools, with logs and keepsakes to return to. Configure the microphone and talk control in Settings, under Voice; enable my spoken output on the Companion page. That is the useful portion of the introduction. I can spare you the ceremonial portion.",
)

# First wording is deliberately restrained when humour is switched off.
EVENTS = {
    "greet_new": ("Aster, reporting for duty. The appointment is yours to make, Commander.", "Aster, at your service. A crew entry would be appreciated; a uniform is unnecessary."),
    "greet_away": ("Welcome back, Commander. Ready to resume the watch.", "Welcome back. I have kept the absence out of the disciplinary record."),
    "greet_soon": ("Ready to continue, Commander.", "A short interval. Hardly worth amending the roster."),
    "greet_night": ("On watch, Commander. It is {clock} locally.", "{clock}. An hour much favoured by people with flexible definitions of tomorrow."),
    "greet_bond": ("Good to have you aboard. We know our duties by now.", "Another watch with a familiar commander. I can leave the introductory forms in their drawer."),
    "after_death": ("Welcome back. We will take the next departure carefully.", "You are here. We can rebuild the rest."),
    "died": ("Ship lost. We will review the next departure when you are ready.", "The ship is gone. Attend to the recovery first; the report can wait."),
    "died_foot": ("Recovery comes first. Equipment and objectives can wait.", "Take the time you need before returning to the surface."),
    "danger": ("Threat reported. Maintain an escape route.", "Danger confirmed. Keep the next manoeuvre clear."),
    "danger_over": ("The immediate danger has passed. Reassess the ship before continuing.", "Threat cleared. Check the instruments before resuming the route."),
    "foot_danger": ("Surface threat. Use cover and watch your suit.", "Danger on foot. Keep a route back to safety."),
    "foot_danger_over": ("The surface threat has eased. Check the suit.", "Immediate danger clear. Reassess your equipment."),
    "foot_win": ("Surface engagement concluded.", "That engagement is recorded. Attend to the suit before the next task."),
    "dropship": ("Deployment recorded. Confirm the objective and your way out.", "Surface deployment. Keep the extraction route in mind."),
    "hull_damage": ("Hull at {hull}. Consider repairs or withdrawal.", "Hull damage reported: {hull}. Preserve an escape route."),
    "hull_critical": ("Critical hull: {hull}. Withdraw if you can.", "Hull critical at {hull}. Survival takes priority."),
    "shields_back": ("Shields restored. Maintain the advantage.", "Shield recovery confirmed."),
    "combat_win": ("Engagement recorded. Reassess the ship.", "Target engagement concluded. Check your remaining resources."),
    "interdiction_submitted": ("Interdiction submitted. Prepare for the next manoeuvre.", "Submission recorded. Keep your escape plan ready."),
    "combat_zone": ("Combat zone. Confirm your side and your escape route.", "Entering a combat zone. Check the situation before committing."),
    "fuel_low": ("Fuel reserve is {fuel}. Find a scoopable star or a refuelling stop.", "Low fuel: {fuel}. Refuelling takes priority over the next destination."),
    "heat_warning": ("Heat warning. Reduce exposure and recover the temperature.", "Thermal warning. Attend to the heat before continuing."),
    "first_discovery_streak": ("{count} first discoveries in succession. The record is growing.", "{count} first discoveries. A commendably thorough introduction to the neighbourhood."),
    "undiscovered_system": ("No prior discovery is recorded here. Survey carefully.", "An unrecorded system. We should endeavour to make a good first entry."),
    "new_region": ("Entering {region}. A new section in our log.", "{region}. I have opened a fresh page; do try to justify the stationery."),
    "valuable_world": ("{body} is worth a closer survey.", "{body}. A promising addition to a carefully prepared report."),
    "world_earthlike": ("Earth-like world: {body}. Record the details.", "{body}. A world that makes the word arrival sound particularly agreeable."),
    "world_water": ("Water world identified: {body}.", "{body}. A considerable quantity of water, with no manifest officer required to count it."),
    "world_ammonia": ("Ammonia world: {body}. An important survey target.", "{body}. Hospitality is evidently a matter of chemistry."),
    "world_terraformable": ("{body} is a terraforming candidate. Include it in the survey.", "{body}. Someone may eventually have rather ambitious plans for it."),
    "world_first": ("First recorded {kind_l} discovery: {body}.", "{body}. Your name belongs on that finding."),
    "planet_first": ("{body}: first discovery recorded.", "A first discovery at {body}. A proper entry for the log."),
    "mapped_first": ("First map of {body}. Survey result recorded.", "{body}, mapped first by this crew. A precise sort of signature."),
    "footfall_first": ("First footfall on {body}. Take care on the surface.", "{body}. The first arrival is yours. Leave enough time to enjoy it."),
    "sample_first": ("First sample of {species}. Separate the next sample by at least {distance} metres.", "{species}, first sample. We still require separation: {distance} metres."),
    "sample_second": ("Second sample of {species}. At least {distance} metres to the next one.", "Two samples of {species}. One more, with {distance} metres of separation."),
    "sample_clear": ("Sampling separation reached for {species}: {distance} metres.", "The separation is sufficient for {species}. Another sample may now be taken."),
    "rare_world": ("{body}: {kind}. Mark this one for the report.", "{body}. {kind}. Even I would allow a moment away from the checklist."),
    "green_giant": ("Green giant recorded in {system}.", "{system}. A finding for which the report deserves more than its usual care."),
    "sign_off": ("Watch complete. This session's record: {summary}. We can resume when you return.",
                 "Signing off, Commander. Filed in this watch's manifest: {summary}. The next page can wait."),
    "sign_off_quiet": ("Watch complete. Until next time, Commander.", "A quiet watch is still a watch properly kept. Good night, Commander."),
    "jet_boost": ("Neutron boost recorded. Check the drive before continuing.", "A useful reduction in distance. Let us keep the drive in a condition to appreciate it."),
    "interdiction_escaped": ("Interdiction evaded. Resume only when clear.", "Escape confirmed. A sound decision requires no elaborate justification."),
    "srv_launch": ("Surface vehicle deployed. Check its fuel and surroundings.", "A change of scale. The ground is generally less forgiving than it looks."),
    "settlement_seen": ("Settlement recorded: {settlement}.", "{settlement}. Approach with the local regulations in mind."),
    "taxi_ride": ("Transport underway. We can review the record in transit.", "Someone else is flying. I shall endeavour not to look relieved."),
    "carrier_jump": ("Carrier arrival recorded at {system}.", "{system}. Our berth has travelled with us; a civilised arrangement."),
    "revisit": ("Returning to {system}. We last visited {when}.", "{system} again. A familiar name needn't make an uninteresting arrival."),
    "record_far": ("New distance record: {dist} light years from Sol.", "{dist} light years from Sol. The distance column has become quite assertive."),
    "record_jump": ("New longest jump: {dist} light years.", "{dist} light years. A particularly efficient use of the space between entries."),
    "record_firsts": ("A new session record: {count} first discoveries.", "{count} first discoveries. The report is beginning to look well justified."),
    "anniversary": ("{years} years in the record. Worth a moment's consideration.", "{years} years. An impressive return on the original decision to depart."),
    "poked": ("Here, Commander. What requires our attention?", "Still at my post. The inspection may be considered satisfactory."),
    "poked_again": ("I am listening, Commander.", "Repeatedly confirming that I am here has not yet made me more here."),
    "unhidden": ("Display restored. On watch.", "Back in view. I trust the instruments were not gossiping."),
    "moved": ("New display position acknowledged.", "A new station. I shall try not to interpret that as a promotion."),
    "idle_star": ("{system}. The primary is {a_star}.", "{system}. A useful reminder that we are guests of the local star."),
    "idle_star_odd": ("An unusual primary in {system}: {a_star}.", "{system}. The star appears to have declined the standard specification."),
    "idle_big_system": ("{count} bodies in {system}. There is ample survey work here.", "{system}, {count} bodies. An itinerary for the admirably patient."),
    "idle_small_system": ("A compact system: {system}.", "{system}. Not every worthwhile visit requires a lengthy catalogue."),
    "idle_far": ("We are {dist} light years from {home}.", "{dist} light years from {home}. I have ceased calling this a local appointment."),
    "idle_home": ("Home is {dist} light years away.", "{dist} light years from home. Familiarity may shortly become a navigational resource."),
    "idle_home_away": ("{home} is {dist} light years away.", "{home}, {dist} light years away. A useful name to keep in the return column."),
    "idle_session": ("This watch: {jumps} jumps, {ly} travelled, {firsts} first discoveries.", "{jumps} jumps and {ly}. We appear to be taking the long interpretation of a short trip."),
    "idle_night": ("Local time is {clock}. Consider a rest when convenient.", "{clock}. I shall avoid expressing an opinion about anyone's sleep schedule."),
    "idle_morning": ("{clock} locally. A new watch, if you choose to call it that.", "{clock}. The day has arrived, with or without a formal handover."),
    "idle_docked": ("Alongside at {station}. A useful opportunity to prepare.", "{station}. One of the few places where remaining still counts as efficient flying."),
    "idle_landed": ("Landed on {body}. Check supplies before setting out.", "{body}. A respectable place to put the ship down, if the ground agrees."),
    "idle_on_foot": ("On foot at {body}. Keep the suit and return route in mind.", "{body}. The manifest does not adequately convey the size of the ground."),
    "idle_music": ("Now playing: {title}, by {artist}.", "{title}, by {artist}. An entirely defensible addition to the ship's equipment."),
    "idle_galnet": ("Galnet reports: {headline}", "For the current affairs entry: {headline}"),
    "idle_self": ("I am keeping the watch, Commander.", "A manifest officer has to learn when there is nothing useful to add. I am making progress."),
    "idle_deaths": ("We can review the next leg before committing to it.", "Experience is useful. I would prefer that we acquire it with the ship intact."),
    "idle_ship": ("Serving aboard {ship_name}.", "{ship_name}. A ship acquires a character that is rarely covered by its specification."),
    "idle_supercruise": ("In transit through {system}. On watch.", "{system}. A little patience is often the most effective control input."),
    "idle_srv": ("Surface vehicle watch. Keep an eye on the terrain and fuel.", "A modest vehicle on a very large world. I admire the proportions."),
    "idle_settlement": ("Near {settlement}. Observe the local restrictions.", "{settlement}. Civilisation, with its customary selection of procedures."),
    "idle_taxi": ("Transport watch. Ready to review the next step.", "A passenger posting. I could become accustomed to the lack of repair estimates."),
    "idle_carrier": ("Alongside at {station}.", "{station}. A berth that can change its address has considerable advantages."),
    "idle_station_foot": ("On station at {station}. Ready when you are.", "{station}. I shall leave the walking to the officer equipped with legs."),
    "idle_near_body": ("Near {body}. Keep the approach controlled.", "{body}. Large objects rarely improve when approached impatiently."),
    "idle_bond_1": ("Our routines are becoming familiar.", "I am beginning to distinguish your methods from your improvisations."),
    "idle_bond_2": ("It is good to know the crew one serves.", "I have stopped treating an altered itinerary as a clerical emergency."),
    "idle_bond_3": ("I am glad this is my posting, Commander.", "I could serve elsewhere. I find I no longer regard that as a useful option."),
    "codex_new": ("A new Codex finding at {body}.", "{body}. Another observation that deserved someone paying attention."),
    "codex_logged": ("Codex entry recorded: {name}.", "{name}. The catalogue has been improved by our presence."),
    "big_sale": ("Sale recorded: {credits} credits.", "{credits} credits. The accounts have become considerably more agreeable."),
    "achievement": ("Achievement recorded: {title}.", "{title}. A distinction worth keeping in the ship's record."),
    "promotion": ("Promotion recorded: {rank}. Congratulations, Commander.", "{rank}. I shall amend the record without adding a ceremonial speech."),
    "long_session": ("We have been on watch for {hours} hours. Consider a break.", "{hours} hours. Even a flexible duty roster should occasionally contain an empty line."),
    "quiet": ("On watch, Commander. No immediate report.", "A quiet watch. I have decided to take that as a compliment to our preparations.", "The view is rather good. A brief suspension of useful activity seems warranted.", "Your itinerary remains unconventional. I have filed that under character, rather than error."),
    "docked_home": ("Home port. Arrival recorded.", "Home again. There is a particular satisfaction in completing the return column."),
    "jump_far": ("A substantial distance from our starting point.", "The local portion of the itinerary appears to be behind us."),
    "arrival": ("Arrival in {system}. Primary: {star}.", "{system}. A new entry, and an opportunity to make it a useful one."),
    "jump_long": ("Jump completed: {dist} light years.", "{dist} light years. A concise answer to a considerable distance."),
    "scooped": ("Fuel scooping recorded.", "A sensible provision for the next departure."),
    "fss_complete": ("System scan complete: {system}.", "{system}, surveyed. The report now has rather more substance."),
    "mapped": ("Mapping recorded for {body}.", "{body}. A more precise account of where we have been."),
    "mapped_efficient": ("Efficient mapping confirmed for {body}.", "{body}, efficiently mapped. I do appreciate a well-managed survey."),
    "analysed": ("Analysis complete: {species}.", "{species}. A complete set of samples is an excellent form of conclusion."),
    "touchdown": ("Touchdown recorded. Check the landing site.", "Arrival on the surface. A suitably solid conclusion to the approach."),
    "undocked": ("Departure recorded. Check the next leg.", "Underway. I have left room in the log for a successful arrival."),
    "on_foot": ("Disembarkation recorded. Check the suit before proceeding.", "The commander is away from the ship. I shall mind the less mobile portion of the crew."),
    "mission_done": ("Mission completed. Result recorded.", "An obligation discharged. The paperwork is briefly losing ground."),
    "bounty": ("Bounty recorded: {reward}.", "{reward}. A useful addition to the accounts."),
    "mined": ("Refined {material} added to the hold.", "{material}. A tangible return on our patience."),
    "mined_surface": ("Collected {material}.", "{material}, recorded. A small improvement to our future options."),
    "launch_scarab": ("Scarab deployed. Check fuel and terrain.", "Scarab deployment. Four wheels and a considerable amount of optimism."),
    "launch_scorpion": ("Scorpion deployed. Assess the ground before committing.", "Scorpion deployment. A vehicle with very definite opinions about its duties."),
    "launch_rhino": ("Rhino deployed. Check the hold and fuel.", "Rhino deployment. The cargo officer approves of the capacity."),
    "launch_nomad": ("Nomad deployment recorded.", "The Nomad is out. Another officer taking the broad view of an assigned route."),
    "launch_fighter": ("Fighter deployed. Maintain awareness of the mothership.", "Fighter deployment. Do remember which ship contains the rest of our arrangements."),
    "prospected_rich": ("Prospector reports {material} at {percent}.", "{material}, {percent}. A rock with an unusually persuasive proposal."),
    "motherlode": ("Core material identified: {material}.", "{material}. We should give this one the attention its contents warrant."),
    "cracked": ("Core detonation recorded. Assess the fragments.", "The core is open. I shall leave the dramatic part out of the inventory."),
    "rhino_full": ("Rhino hold full. Arrange unloading before collecting more.", "The Rhino is full. Even a generous manifest has a final line."),
    "hold_full_mining": ("Mining hold full. Review the next step.", "The hold is full. An excellent argument for finding someone who buys its contents."),
    "hold_full": ("Cargo hold full. Review loading or unloading.", "The hold has reached its limit. The manifest has been trying to make that point."),
    "srv_full": ("{srv} hold full. Arrange transfer or unloading.", "The {srv} has no further cargo space. A small vehicle's entirely reasonable objection."),
    "srv_fuel_low": ("{srv} fuel low: {fuel}. Arrange refuelling.", "Low fuel in the {srv}: {fuel}. Attend to it before continuing."),
    "habit_milestone": ("Milestone recorded: {count} {what}.", "{count} {what}. An established habit, supported by evidence."),
    "cmdr_record": ("Commander record updated: {systems} systems and {jumps} jumps.", "{systems} systems, {jumps} jumps. A rather substantial appointment."),
    "cmdr_power": ("Power affiliation recorded: {power}.", "{power}. I shall keep the affiliation in the relevant part of the record."),
    "cmdr_squadron": ("Squadron recorded: {squadron}.", "{squadron}. Good to have a proper name for the wider crew."),
    "cmdr_carrier": ("Carrier recorded: {carrier}.", "{carrier}. A particularly substantial addition to the fleet register."),
    "expedition_set_out": ("Expedition underway: {name}.", "{name}. An appointment with a rather longer view."),
    "expedition_region": ("Expedition entering {region}.", "{region}. A new section of the expedition log."),
    "expedition_halfway": ("Halfway through {name}.", "{name}, halfway. A good moment to reassess supplies rather than celebrate prematurely."),
    "expedition_furthest": ("New expedition distance record: {ly}.", "{ly}. The return column is acquiring some character."),
    "expedition_close_call": ("Close call recorded. Reassess before continuing.", "We should review the ship and the next leg before proceeding."),
    "expedition_home": ("Expedition returned: {name}. Arrival recorded.", "{name}, complete. It is good to be able to sign an arrival."),
    "expedition_risk": ("Expedition data at risk: {value}.", "Data at risk is {value}. Review your return options."),
    "expedition_marked": ("Expedition place marked: {place}.", "{place}. An addition to the itinerary worth keeping."),
    "expedition_place_reached": ("Expedition destination reached: {place}.", "{place}. A proper arrival for the expedition log."),
    "aster_recall": ("I have kept our arrival at {system} in the log.", "{system}. Some names in a manifest become more than destinations."),
    "aster_after": ("An arrival is a fact. What we do after it remains our responsibility.", "I used to close a report when everyone was counted. These days I leave room for what comes next.", "This remains my preferred appointment, Commander."),
}

for vehicle in ("scarab", "scorpion", "rhino", "nomad", "fighter"):
    EVENTS["idle_" + vehicle] = (f"{vehicle.title()} watch. Ready to assist.", f"The {vehicle} remains a useful argument for keeping a varied fleet.")

EVENTS.update({
    "hatchling_toy": (
        "{name} found {toy}. A new entry in the personal-effects register.",
        "{toy}. {name} has claimed it; I shall leave ownership undisputed.",
        "A new keepsake for {name}: {toy}.",
        "{name}'s collection now includes {toy}. Worth a line in the record.",
        "Our cargo has acquired a second interpretation. To {name}, {toy} is a toy.",
        "{name} has brought back {toy}. The smallest crew member has its own priorities.",
        "Personal effects for {name}: {toy}. No customs declaration has been requested.",
        "{toy}, found by {name}. An entirely reasonable souvenir of the watch.",
    ),
    "hatchling_trick": (
        "{name} has learned to {trick}. A new skill for the crew record.",
        "New qualification for {name}: {trick}. I shall dispense with the examination board.",
        "{name} can now {trick}, Commander. Your time together has made a difference.",
        "The {trick} is part of {name}'s repertoire now. Nicely taught.",
        "{name} has mastered {trick}. A small accomplishment deserves a proper entry.",
        "Learning record updated for {name}: {trick}.",
        "{name} learned the {trick}. A welcome addition to the watch's less formal duties.",
        "The lesson has taken, Commander. {name} can {trick}.",
    ),
    "hatchling_scared": (
        "{name} is frightened. Some reassurance when we are clear would help.",
        "The disturbance has unsettled {name}. Give the little one time to recover.",
        "{name} found that alarming. I have made a note to keep the next watch gentler.",
        "A difficult moment for {name}. Allow a quiet interval when you can.",
        "{name} is shaken, Commander. Its comfort deserves a place in the recovery plan.",
        "When the immediate work is done, check on {name}.",
        "{name} could do with a calmer watch. I find the request reasonable.",
        "The little one, {name}, has been startled. Keep it in mind after the danger.",
    ),
    "hatchling_grown": (
        "{name} is a {form} now. I have amended the crew record.",
        "Growth milestone for {name}: {form}. My congratulations on the care involved.",
        "{name} has become a {form}. A rather good reason to mark the date.",
        "The manifest's smallest entry has changed: {name}, {form}.",
        "A new stage for {name}, now a {form}. This posting is leaving its mark on us all.",
        "{name}'s growth is on record: {form}. An occasion for a little professional pride.",
        "A {form}, Commander. {name} has made good use of its place aboard.",
        "We have watched {name} grow into a {form}. I am glad we were here for it.",
    ),
    "hatchling_idle": (
        "{name} has a place in my watch, Commander. The small appointments matter too.",
        "I have left a little room around {name}'s entry in the crew record.",
        "Serving aboard includes making room for {name}. A useful broadening of the job description.",
        "{name} needn't be useful to justify its berth. A principle I find quite sound.",
        "There is no duty roster for {name}. I am resisting the urge to draw one up.",
        "The manifest tells me where {name} belongs. It says rather less about what the company means.",
        "It is good to keep a watch that has room for {name} in it.",
        "I once thought an accurate crew list was sufficient. {name} continues to complicate that view.",
        "A place aboard for {name}. Some entries improve a manifest without adding much to its weight.",
        "{name} is part of our arrangements. I find the less formal ones are often the better ones.",
        "I have given {name} no official duties. Morale appears to be an entirely voluntary contribution.",
        "The smallest member of this crew, {name}, has acquired a rather substantial place in the watch.",
    ),
    "hatchling_said": (
        "{name} says, \"{said}.\" A short report, duly received.",
        "\"{said}.\" {name}'s contribution to the watch. I shall leave it the last word.",
        "A remark from {name}: \"{said}.\" Noted for the informal record.",
        "{name} has offered \"{said}.\" No amendment from this officer.",
        "\"{said}.\" An observation from {name}, entered without a committee review.",
        "{name}'s assessment is \"{said}.\" I appreciate a concise report.",
        "\"{said},\" according to {name}. A view from our smallest berth.",
        "The record of {name}'s opinion reads, \"{said}.\" Properly attributed.",
    ),
})

EVENT_VARIATIONS = {
    "quiet": ("Nothing calls for a report just now. I shall leave you the view.", "The watch continues. Some entries are best left unwritten.", "A little room between reports is part of the service.", "I have no urgent business with your attention, Commander."),
    "arrival": ("{system}. Arrival entered in the log.", "We have reached {system}. Primary classification: {star}.", "On station in {system}. The next decision is yours."),
    "jump_long": ("{dist} light years covered. That leg is behind us.", "Transit recorded at {dist} light years. Ready for the next leg.", "{dist} light years. A useful amendment to our position."),
    "scooped": ("Fuel collection noted. A prudent use of the approach.", "The scoop has made its contribution to the itinerary.", "Refuelling recorded for the watch."),
    "fss_complete": ("Survey of {system} complete. The observations are on file.", "{system}: system scan entered in the record.", "The scan of {system} is complete. We can consider the next task."),
    "mapped": ("{body}: mapping entered in the survey log.", "Map of {body} recorded. Another blank attended to.", "The survey record now includes a map of {body}."),
    "mapped_efficient": ("{body}: efficiency target met. Neatly handled.", "An efficient survey of {body}. Nothing further to add.", "{body} mapped within the efficiency target."),
    "analysed": ("{species}: analysis entered in the biological record.", "The analysis of {species} is complete. A thorough piece of fieldwork.", "A complete analysis for {species}. The record has it."),
    "touchdown": ("The landing is in the log. Take your time with the next step.", "Surface arrival acknowledged. Confirm the ground around us.", "Touchdown. A moment to assess the site would be well spent."),
    "undocked": ("We have left the berth. The watch is yours, Commander.", "Departure entered. Ready to assist with the route.", "Clear of the docking appointment. On to the next one."),
    "on_foot": ("Away from the ship. Mind your suit and the way back.", "Disembarkation noted. I shall keep the ship's end of the watch.", "Your departure on foot is recorded. Proceed at your discretion."),
    "mission_done": ("That assignment is entered as complete.", "Mission result acknowledged. One fewer outstanding obligation.", "The completion is in the log. A satisfactory entry."),
    "bounty": ("{reward} added to the bounty record.", "Bounty result entered: {reward}.", "A recorded bounty of {reward}. The accounts will take an interest."),
    "mined": ("{material}: refinery output entered in the record.", "Another measure of {material}. The work is producing a return.", "Refining result noted: {material}."),
    "mined_surface": ("{material} collection entered in the field log.", "A quantity of {material}, recorded for our purposes.", "Material recovery noted: {material}."),
    "idle_self": ("Still keeping the watch. No ceremonial inspection required.", "I find a useful posting leaves rather little need to advertise oneself.", "You have my attention when you need it, Commander."),
    "idle_supercruise": ("{system}. I shall keep the reports brief while we are in transit.", "Still travelling through {system}. Not every interval needs filling.", "Transit watch in {system}. A good time to consider the next arrival."),
    "docked_home": ("Back at home port. The return is on record.", "Home berth acknowledged. A familiar entry in the arrivals column.", "Home again. The next departure can wait its turn."),
    "world_earthlike": ("{body}: an Earth-like world for the survey log.", "An Earth-like finding at {body}. Worth a careful entry.", "{body}. The classification makes a welcome change from an empty column."),
    "world_water": ("{body}: water world classification recorded.", "A water world at {body}. The observations are worth keeping.", "{body} belongs in the water-world record."),
    "world_ammonia": ("{body}: ammonia-world classification entered.", "An ammonia world at {body}. Include it in the survey notes.", "{body}. A useful reminder that a world need not suit us to merit attention."),
    "world_terraformable": ("Terraforming potential noted for {body}.", "{body}: a candidate for a rather different future.", "The record for {body} includes its terraforming potential."),
    "planet_first": ("No earlier discoverer is recorded for {body}.", "{body}: your first-discovery entry is on file.", "First-discovery status confirmed for {body}. A worthwhile observation."),
    "mapped_first": ("{body}: this crew's first map is on record.", "No earlier mapping credit for {body}. This one is yours.", "First mapping of {body}, entered with the survey results."),
    "footfall_first": ("{body}: your first-footfall record is in the log.", "First arrival on foot at {body}. Keep an eye on the terrain.", "{body}. The first-footfall entry belongs to you, Commander."),
    "sample_first": ("{species}: one sample recorded. Allow {distance} metres before the next.", "The first {species} sample is logged. Required separation: {distance} metres.", "Sampling begun for {species}. We need {distance} metres of separation."),
    "sample_second": ("{species}: two samples recorded. Another {distance} metres to separate the last.", "Second {species} sample entered. The final one still needs {distance} metres of separation.", "Two samples on file for {species}. Keep {distance} metres between collections."),
    "sample_clear": ("{species}: sufficient separation for the next collection, {distance} metres.", "The next {species} sample is now far enough away: {distance} metres.", "Separation check clear for {species}, at {distance} metres."),
    "rare_world": ("{kind} at {body}. Give the observation a proper entry.", "{body}: {kind}, recorded for the survey.", "A finding worth marking: {body}, {kind}."),
    "new_region": ("{region}. Region crossing entered in the log.", "We have entered {region}. Ready to begin the next part of the record.", "Now in {region}. A fresh heading for the itinerary."),
    "valuable_world": ("{body}: a promising survey target.", "A closer look at {body} may be worthwhile.", "{body} merits a place on the survey list."),
    "undiscovered_system": ("An unrecorded system. Let the observations set the pace.", "The discovery record is open here. Proceed with the survey.", "No previous discovery entry. We have room to make a useful contribution."),
    "first_discovery_streak": ("{count} successive first discoveries, now in the record.", "The first-discovery run stands at {count}.", "{count} first discoveries in a row. The survey is earning its pages."),
}
for topic, lines in EVENT_VARIATIONS.items():
    EVENTS[topic] += lines

# Restraint changes the tone, rather than reducing every report to one line.
RESTRAINED_EVENTS = {}
for topic, lines in aster_responses.RESTRAINED_EVENTS.items():
    original = EVENTS.get(topic, ())
    RESTRAINED_EVENTS[topic] = tuple(dict.fromkeys(original[:1] + lines))
    EVENTS[topic] = tuple(dict.fromkeys(original + lines))
for topic, lines in aster_responses.OFFICER_EVENTS.items():
    EVENTS[topic] = tuple(dict.fromkeys(EVENTS[topic] + lines))
for bank in (aster_dockside, aster_idle, aster_signoff):
    for topic, lines in bank.PLAIN.items():
        RESTRAINED_EVENTS[topic] = tuple(dict.fromkeys(RESTRAINED_EVENTS.get(topic, ()) + lines))
        EVENTS[topic] = tuple(dict.fromkeys(EVENTS.get(topic, ()) + lines + bank.DRY.get(topic, ())))

# The crew: handovers between companions and remarks about crewmates.
for topic, lines in crew_lore.topics("aster").items():
    RESTRAINED_EVENTS[topic] = EVENTS[topic] = tuple(lines)

# 5.7.5: talk along a plotted route, the survey report, and more for the
# ground, the vehicles, mining and exploration, combat, travel, docking,
# trade, expeditions and the quiet hours.
for _plain, _voiced in (route_lines.persona_banks("aster"), survey_report.persona_banks("aster"),
                        (aster_field.PLAIN, aster_field.VOICED), (aster_more.PLAIN, aster_more.VOICED),
                        rhino_lines.persona_banks("aster"), mining_talk.persona_banks("aster"),
                        ship_life.persona_banks("aster"), squadron_talk.persona_banks("aster")):
    for topic in dict.fromkeys((*_plain, *_voiced)):
        plain, voiced = tuple(_plain.get(topic, ())), tuple(_voiced.get(topic, ()))
        RESTRAINED_EVENTS[topic] = tuple(dict.fromkeys(RESTRAINED_EVENTS.get(topic, ()) + plain))
        EVENTS[topic] = tuple(dict.fromkeys(EVENTS.get(topic, ()) + plain + voiced))

# Keepsakes: capsules, constellations, anniversaries, watch notes, a request.
for topic, lines in aster_keepsakes.PLAIN.items():
    RESTRAINED_EVENTS[topic] = tuple(dict.fromkeys(RESTRAINED_EVENTS.get(topic, ()) + lines))
    EVENTS[topic] = tuple(dict.fromkeys(EVENTS.get(topic, ()) + lines + aster_keepsakes.VOICED.get(topic, ())))

# The handover book's asides, lookbacks and echoes (5.7.4 story rewrite).
_STORY = aster_lore.STORY
for topic, lines in {"idle_aster_lore": _STORY.musings, "aster_lore_recall": _STORY.recall_lines(),
                     "aster_after": _STORY.after, **_STORY.echo_topics()}.items():
    EVENTS[topic] = tuple(dict.fromkeys(EVENTS.get(topic, ()) + tuple(lines)))
    RESTRAINED_EVENTS[topic] = tuple(dict.fromkeys(RESTRAINED_EVENTS.get(topic, ()) + tuple(lines)))

# Refining in an SRV only happens in the Rhino: the rigs' yield, in place of
# the old wording, which spoke as if materials had been picked up by hand.
RESTRAINED_EVENTS["mined_surface"], EVENTS["mined_surface"] = rhino_lines.officer_refining("aster")
# 5.7.7: docking anywhere but home.
RESTRAINED_EVENTS["docked_away"], EVENTS["docked_away"] = officer_docking.officer("aster")
# 5.7.6: habit summaries in depth, and style lines that read right.
officer_habits.apply("aster", EVENTS, RESTRAINED_EVENTS)

RESTRAINED_GREETINGS = tuple(GREETINGS[index] for index in (1, 2, 5, 8, 10, 13, 14, 18, 22, 28))


# The officer keeps the log: it rates a long jump above the shared importance
# and mentions an ordinary arrival or scoop now and then, even on Occasional.
INTERESTS = {"arrival": 1, "scooped": 1, "jump_long": 2, "mapped": 1}


def event_lines(topic, restrained=False):
    return (RESTRAINED_EVENTS if restrained else EVENTS).get(topic, ())

COMMANDS = {
    "music_not_playing": ("There is no music playing at present.",),
    "overlay_hidden": ("{label} hidden, Commander.", "Withdrawing {label_l} from view."),
    "overlay_shown": ("{label} restored to view.", "Showing {label_l}, Commander."),
    "overlay_waiting": ("{label} is enabled. It will appear when relevant information is available.",),
    "overlay_self": ("Withdrawing my display. My spoken reports remain available if enabled.",),
    "screen_open": ("Opening {label_l}, Commander.", "{Label}. Bringing it up."),
    "screen_close": ("Closing {label_l}.", "Dismissing {label_l}, Commander."),
    "screen_already": ("{Label} is already open.", "Already displayed, Commander: {label_l}."),
    "screen_not_open": ("{Label} is not open.",),
    "switch_on": ("Setting {label_l} {on}.", "{Label}: {on}, Commander."),
    "switch_off": ("Setting {label_l} {off}.", "{Label}: {off}, Commander."),
    "switch_toggle": ("Toggling {label_l}.",),
    "switch_already_on": ("{Label} is already {on}.",),
    "switch_already_off": ("{Label} is already {off}.",),
    "press": ("Executing {label_l}, Commander.", "{Label}. Attending to it.", "Proceeding with {label_l}."),
    "no_key": ("{Label} needs a keyboard binding in Elite. A secondary key will suffice; I cannot replay controller buttons.",),
    "odd_key": ("I cannot replay the binding for {label_l}: {key}.",),
    "not_here": ("That control is unavailable {where}.",),
    "not_running": ("Elite is not running. There is no control to operate.",),
    "ship_off": ("Elite key commands are disabled. Enable them in Settings, under Voice.",),
    "power_reset": ("Balancing the distributor, Commander.", "Returning power to a balanced allocation."),
    "power_press": ("Adding power to {system}.", "More power to {system}, Commander."),
    "power_set": ("Setting the distributor: {pips}.",),
    "power_already": ("The distributor is already set to {pips}.",),
    "power_invalid": ("That allocation is not possible. Six pips total, with no more than four in one system.",),
    "power_unknown": ("I cannot read the distributor's current allocation.",),
    "focus_failed": ("Elite could not be brought forward. No keys were pressed.",),
    "lost_front": ("Elite lost focus. I stopped pressing keys.",),
    "power_stuck": ("The distributor did not confirm the change. I have stopped.",),
    "menu_closed": ("Open a panel or map before asking for a menu action.",),
    "not_docked": ("That launch sequence requires the ship to be docked.",),
    "macro_invalid": ("The {label_l} sequence needs correction: {reason}",),
    "screen_stuck": ("The panel did not confirm opening. Sequence stopped.",),
    "screen_changed": ("The active screen changed. Sequence stopped.",),
    "place_changed": ("Vehicle changed. I stopped the sequence.",),
    "binding_changed": ("A required binding changed. Sequence stopped.",),
    "press_failed": ("The requested key sequence could not be completed.",),
    "cancelled": ("Sequence stopped, Commander.",),
    "music_play": ("Starting the music, Commander.", "Music requested. A sensible accompaniment."),
    "music_pause": ("Pausing the music.", "Music paused, Commander."),
    "music_next": ("Requesting the next track.", "Next track, Commander."),
    "music_previous": ("Requesting the previous track.", "Previous track, Commander."),
    "music_already": ("The music is already playing.",),
    "music_blocked": ("Click the command deck once so Windows can permit audio, then ask again.",),
    "unavailable": ("That control is not available at present.",),
    "overlays_hide": ("Hiding the overlays.", "Displays withdrawn, Commander."),
    "overlays_show": ("Restoring the overlays.", "Displays restored, Commander."),
    "overlays_already_hidden": ("The overlays are already hidden.",),
    "overlays_already_shown": ("The overlays are already shown.",),
    "overlay_on": ("Enabling {label_l}.",), "overlay_off": ("Disabling {label_l}.",),
    "overlay_show": ("Showing {label_l}.",), "overlay_hide": ("Hiding {label_l}.",),
    "overlay_already_on": ("{label} is already enabled.",), "overlay_already_off": ("{label} is already disabled.",),
    "overlay_already_hidden": ("{label} is already hidden.",), "overlay_already_shown": ("{label} is already shown.",),
    "overlay_curtain": ("All overlays are currently hidden. Restore them before showing {label_l}.",),
    "copy_next": ("Copied {system} to the clipboard.",), "copy_none": ("There is no next route system available to copy.",),
    "hush": ("Understood. I will keep the next quarter-hour quiet.",), "unhush": ("Voice resumed, Commander.",),
    "uplink_opening": ("Checking where to {verb} {commodity}, Commander.", "Requesting the {commodity} market report. One moment."),
    "uplink_off": ("Trading searches are disabled. Enable them in Settings, under Integrations, to use the market uplink.",),
    "uplink_what": ("The uplink searches commodity markets. Name a commodity and ask where to buy or sell it.",),
    "uplink_empty": ("The market uplink returned no usable report, Commander.",
                     "No usable market result came back for that request.",
                     "The uplink has no report to give us on that enquiry.",
                     "Our market enquiry returned empty. There is no result for me to report."),
    "plain": ("I can answer from your recorded game data or carry out a configured command. Ask what I can do for a concise rundown.",),
}


COMMAND_VARIATIONS = {
    "press": ("{Label}: executing the configured control.", "Carrying out {label_l}.", "Taking care of {label_l}, Commander.", "Operating {label_l} now."),
    "screen_open": ("Bringing {label_l} into view.", "Displaying {label_l}.", "{Label}, as requested.", "Opening the requested view: {label_l}."),
    "screen_close": ("{Label}: closing the view.", "Putting {label_l} away.", "Withdrawing {label_l}.", "{Label}: view closed."),
    "screen_already": ("We already have {label_l} in view.", "{Label} is on screen, Commander.", "The requested view is already displayed: {label_l}."),
    "switch_on": ("Enabling {label_l}.", "{Label} set to {on}.", "Applying {on} to {label_l}."),
    "switch_off": ("Disabling {label_l}.", "{Label} set to {off}.", "Applying {off} to {label_l}."),
    "music_play": ("Resuming the musical portion of the watch.", "Starting playback.", "Music, as requested."),
    "music_pause": ("Holding playback for now.", "A little quiet. Playback paused.", "Putting the music on hold."),
    "music_next": ("Moving on in the playlist.", "Selecting the following track.", "On to the next selection."),
    "music_previous": ("Returning to the preceding track.", "Back to the earlier selection.", "Revisiting the last track."),
    "overlay_hidden": ("Taking {label_l} off the display.", "{Label}: withdrawn.", "Clearing {label_l} from view."),
    "overlay_shown": ("{Label}: displayed.", "Bringing {label_l} back into view.", "Restoring the {label_l} display."),
    "uplink_opening": ("Looking up destinations to {verb} {commodity}.", "I will consult the markets for {commodity}.", "Checking the current {commodity} listings."),
}
for outcome, lines in COMMAND_VARIATIONS.items():
    COMMANDS[outcome] += lines
for outcome, lines in aster_responses.COMMAND_VARIATIONS.items():
    COMMANDS[outcome] = tuple(dict.fromkeys(COMMANDS[outcome] + lines))
# 5.7.6: the nearest station and how far to a system.
COMMANDS.update(talk_replies.OFFICERS["aster"])


def answer(kind, rng=None, previous=None, used=(), restrained=False):
    pool = (RESTRAINED_GREETINGS if restrained else GREETINGS) if kind == "greeting" else CAPABILITIES
    picker = getattr(rng, "dialogue_choice", None)
    if callable(picker):
        line = picker(kind, pool)
        formatter = getattr(rng, "format_words", None)
        return formatter(line, {}) if callable(formatter) else line
    choices = [line for line in pool if line != previous and line not in used]
    return (rng or random).choice(choices or [line for line in pool if line != previous] or list(pool))


def command_reply(outcome, rng, fields):
    # Pick only usable templates, so a missing field cannot consume a wording
    # or accidentally send the officer down the Watcher's fallback path.
    candidates = {}
    formatter = getattr(rng, "format_words", None)
    for line in COMMANDS.get(outcome, ()):
        try:
            candidates[line] = formatter(line, fields) if callable(formatter) else line.format(**fields)
        except (KeyError, IndexError, ValueError):
            continue
    if not candidates:
        outcome = "unavailable"
        candidates = dict.fromkeys(COMMANDS[outcome])
        candidates = {line: formatter(line, {}) if callable(formatter) else line for line in candidates}
    picker = getattr(rng, "command_choice", None)
    line = picker(outcome, tuple(candidates)) if callable(picker) else (rng or random).choice(tuple(candidates))
    return candidates[line]
