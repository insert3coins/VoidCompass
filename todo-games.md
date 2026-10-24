# Games page: what to add next

Ideas for more cabinets on the Games page (5.6.3 started it with Thargoid Swarm).
Each one is an 80s arcade classic redone as our own game in Elite's world:
our own code, our own names and pictures, nothing copied from the originals.

Every game is a folder in `web/games/<id>/` with a `game.json`, and gets a
card picture in `assets/gamecards/<id>.png` at **1200 × 1350** (8:9).

NOTE ABOUT ART, lets use screenshots we take of each game instead of placing assets/gamecards imagaes (too much work to draw each one etc) update the already games in place

Also no joystick support needed, if we have it just for games, remove it, mouse steering is fine if needed and click to fire
yes update thargoid swarm screenshot with the new plan


## Before the next game: a shared kit

Thargoid Swarm has its sound, input, loop and messages to the deck all inside
its own `game.js`. Before game two, move the common parts out so each game
stays small:

- [x] `web/games/kit/` (no `game.json`, so it never gets a card), loaded by each game with `<script src="../kit/…">`:
  - [x] `sound.js`: the synthesised 8-bit sounds (tone, hiss, mute)
  - [x] `cabinet.js`: fitting the screen, a fixed 60-steps-a-second loop, pausing when the deck asks or the window loses focus, and the ready/hello/over/mute messages
  - [x] `input.js`: keys, mouse and touch in one place
  - [x] `draw.js`: glow lines, wireframe helpers, text, and the Elite combat-rank table
- [x] Move Thargoid Swarm onto the kit (it should play exactly the same)
- [x] An optional CRT look (scanlines and a slight curve), switchable per game

## The games

6:
### Docking Computer (Elite, 1984)
The original Elite's famous moment: match the Coriolis station's spin and fly through the slot. Wireframe 3D, green on black like the 1984 original.
- [x] A spinning Coriolis station with its slot, approached in first person
- [x] Match roll, line up and throttle down: too fast or off-angle and you scrape and lose shields
- [x] Traffic leaving the slot, and later Dodecahedron and Ocellus stations
- [x] A score from time, speed at the slot and hull left
- [x] Optional: the Blue Danube plays while you're lined up, synthesised (public domain)

4:
### Rock Rats (Asteroids, 1979)
Mining in a vector asteroid field. Break rocks into smaller rocks, but the cores are worth more than the gravel.
- [x] Thrust-and-rotate flight that wraps around the screen, vector-drawn
- [x] Rocks split in three sizes; some have cores (bonus) and some are pristine (more drops)
- [x] Collect fragments with limpets for points; a full hold banks them
- [x] Pirates now and then: a Sidewinder, or a Viper that's harder to shake

3:
### Touchdown (Lunar Lander, 1979)
Land the ship on a planet's pad without running out of fuel.
- [x] Side-on terrain with landing pads worth different scores
- [x] Thrust, rotation and a fuel gauge
- [x] Gravity from the real body you're at: if the journal says you're near a 2.4 g world, the game lands at 2.4 g, and the deck sends the gravity in its hello. Away from any body, a random world.
- [x] High-g warnings (red text when gravity is over 2 g, like the game)

5:
### Station Defence (Missile Command, 1980)
Thargoid caustic missiles rain on a surface settlement; shoot them down with point defence before they reach the buildings.
- [x] Three turrets, aimed with the mouse; shots burst where you click
- [x] Missiles that split, faster waves, and a Thargoid Scout that drops seeds
- [x] Buildings you can lose and win back with bonus points

7:
### Canyon Run (Scramble, 1981)
Fly a side-scrolling canyon like the Buckyball racers: low, fast, and running out of fuel.
- [x] Terrain that scrolls, with fuel depots to shoot for refills
- [x] Ground turrets, overhangs and narrow gaps
- [x] A clock: a run is scored on time and how low you dared to fly

8:
### No Fire Zone (Frogger, 1981)
Cross a busy station approach with traffic in every lane. Don't speed, don't bump anything, and don't loiter in the slot.
- [x] Lanes of ships moving at different speeds, plus lanes of drifting cargo canisters to hop across
- [x] Station rules: bump someone and you're fined; fire and the station opens up on you
- [x] Five landing pads to fill per level

9:
### Shield Breaker (Breakout, 1976)
Bounce a shot off your ship to break a capital ship's shield panels, then its hull plates.
- [x] Panels that take two hits, armoured plates and power-ups (multiball, wider ship)
- [x] Each level a different ship's silhouette (Farragut, Majestic, Thargoid Titan)

2:
### Supercruise Runner (Out Run, 1986)
A pseudo-3D race to a station in supercruise: dodge stars and planets, keep the speed up, and hit the seven-second slowdown point. It goes with 5.6.2's synthwave.
- [x] Road-style perspective with stars and planets as hazards
- [x] Throttle, the blue zone and an overshoot
- [x] A synthwave look and a looping synthesised tune

### Trumble Trouble (Elite, 1984)
Elite's own secret: furry Trumbles that multiply in your hold. A one-screen catch-them-all before they fill the ship.
- [x] Trumbles that breed if you leave them, and a hold that fills up
- [x] Capture them, vent them, or sell them at a station: a silly score attack

1:
### Tamagochi styled elite game: Hatchling
A pocket pet that lives in your cockpit, Tamagotchi-style, but Elite Dangerous through and through. It isn't a round-and-done arcade game: it keeps going between sessions, and a lot of how it fares comes from how you really play.

**What it is:** pick one at hatching (each with its own looks and habits):
- [x] **A Thargoid larva**, from a strange egg found "in a damaged Thargoid structure". It hums, glows green when happy, and hates Guardian things.
- [x] **A Remlok companion bot**: a little maintenance drone that beeps and wants upgrades, not food.
- [x] **An exobiology sample** (a bacterium, a tubus, a fungoida colony) grown in a sample canister: it needs light, warmth and the right atmosphere.

**Its needs** (the Tamagotchi part), each a bar on its little screen:
- [x] **Hunger**: feed it from a small larder (snacks, meals and treats such as Coffee, Tea, Fish and Lavian Brandy)
- [x] **Mood**: play with it (a tiny minigame: catch the Limpet, guess where the Thargon went)
- [x] **Clean**: it makes a mess, so you vent the hold
- [x] **Health**: neglect it and it gets ill; medicine (Basic Medicines, Agronomic Treatment for a sample) cures it
- [x] **Sleep**: lights off, and it sleeps through a carrier jump

**Your game feeds it** (read from the journal, nothing sent anywhere):
- [x] Buying food commodities at a market stocks its larder (buy Coffee, and it gets coffee)
- [x] Exploring keeps it curious and happy: new systems, first discoveries and codex entries
- [x] Combat scares it (shields down, hull damage), and a rebuy makes it very upset
- [x] A Thargoid larva gets excited near Thargoid sites, and Guardian sites unsettle it
- [x] Docking somewhere new is a little treat; long supercruise bores it

**Growing up:** egg, hatchling, juvenile, adult, over real days. How you raised it picks its adult form (well fed and explored versus neglected and battle-scarred); a few rare forms make it a collection.

**Decisions to make before building:**
- [x] Does it get hungry in real time while VoidCompass is closed (true Tamagotchi), only while you're playing Elite, or only while the deck is open? (yes realtime)
- [x] Can it die? A real Tamagotchi can. A gentle version could have it "go into hibernation" and be woken with care instead. (no death, well kinda, but we will have a why to bring it back to life, but then if no after a certian amount of time)
- [x] Just on the Games page, or also as a small overlay (in Overlay Studio, following overlayfix.md) so you can see it while you fly? (overlay for it yea it goes in Overlay Studio and follows overlayfix.md.)
- [x] One per commander (like the Watcher's memory), saved in the profile folder.
- [ ] Does the Watcher notice it? (It could have opinions about a Thargoid larva in the hold.) <--- hold on this idea for later 

## Ideas that go with any game
These are after we got our games in, we will circle back to this

- [ ] **The Watcher notices** a new best score and says something about it (only once per best, and only if it's awake)
- [ ] **Achievements** for firsts: first Interceptor downed, first Elite rank and so on, in the existing achievements overlay
- [ ] **Attract mode**: a card shows a moving preview of the game while you hover over it
- [ ] **Two players** on one keyboard, for the games that suit it (Shield Breaker, No Fire Zone)
- [ ] **A Games line in the Local API** (`GET /games`: games and best scores) for Stream Deck or OBS
- [ ] **A Galnet-style "high score table" overlay** for streaming: your best run as an overlay while you play. If built, it goes in Overlay Studio and follows overlayfix.md.

## Rules for every game

- Our own code, names and drawings. The 80s games give the ideas, never code, artwork, sounds or trademarked names.
- English, offline, no AI, no keys: a game can't reach the network (its CSP says so).
- The same speed on any monitor (fixed steps), pause on blur, M for sound.
- A card picture at 1200 × 1350, and a `game.json` with controls.
- Tests: the game loads under its real policies, starts, and reports a score.


there are 10 of these, when adding them do it in order, Alphabelitise the layout etc
Start with the screenshot thing with the already one that's done