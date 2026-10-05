# TODO: Trading

A full trading system, with **Spansh** as the online source. No local price database: every price, route and station comes from Spansh, and Spansh keeps them fresh from the EDDN feed.

## Ground rules

- [ ] **Online only, on request.** Search when the commander asks, never in the background. Spansh is one volunteer's service, so keep traffic light, cache replies for the session, and identify ourselves with our usual `User-Agent`.
- [ ] **Off during replay** and the first-run history scan.
- [ ] **Real figures only.** Prices come from Spansh with their age shown, and cargo and credits come from the journal. Never guess either.
- [ ] **Fail politely.** If Spansh is down or slow, say so in the tab and keep the last results on screen.
- [ ] **Setting:** use the existing Spansh integration switch in Settings › Integrations if there is one; otherwise add a "Trading searches (Spansh)" switch, registered in the `config.py` `PROFILE_*` tuples.

## What we already have

- `services/spansh.py`:
  - `submit_and_poll()`, Spansh's job pattern (POST a form, then poll `/api/results/<job>`). The fleet carrier, neutron and road-to-riches routes already use it.
  - `resolve_system()` and `station_search()`.
- `mining/mining_data.py` already calls `https://spansh.co.uk/api/commodity/sell/<system>/<commodity>/<amount>`. Reuse that pattern, and move it into `services/spansh.py` if it gets a second user.
- From the journal: live cargo (`Cargo.json`), credits, cargo capacity and pad size (`Loadout`), the current system and station, and jump range.

## 1. Check the Spansh endpoints first

The trade router isn't a documented public API; it's what spansh.co.uk/trade uses. Confirm the details by watching the site's own network calls before writing any code.

- [ ] **Trade route:** probably `POST /api/trade/route`, then poll `/api/results/<job>`. Confirm the parameter names. Expected:
  - `system`, `station`
  - `starting_capital`, `max_cargo`, `max_hop_distance`, `max_hops`
  - `max_system_distance` (distance from arrival, in light seconds), `max_price_age`
  - `requires_large_pad`, `allow_planetary`, `allow_player_owned` (fleet carriers), `allow_prohibited`, `permit`, `unique`
- [ ] **Commodity buy and sell searches:** we know `GET /api/commodity/sell/...` works. Find the matching endpoint for buying, if there is one.
- [ ] **Station market:** a single station's full market, for the "this station" view.
- [ ] Save one real reply of each kind as a test fixture under `tests/`, then write the parsers against those fixtures.

## 2. The Trading tab

A new main-menu tab, in the same style as BGS and Colonisation (a hero area with sub-tabs).

- [ ] **Route planner** (the Spansh trade router):
  - A form pre-filled from the journal: the current system and station, cargo capacity, credits, pad size, and jump range for the hop distance. Everything stays editable.
  - Options: number of hops (1 is a single run, more is a multi-hop), maximum hop distance, maximum distance from arrival, price age, planetary ports, fleet carriers, permit systems, illegal goods, and "don't repeat a station".
  - The result shows each hop's commodity, how much to buy, buy and sell prices, profit per tonne and per hop, and distances. A total sits at the top, with each price's age shown.
  - Buttons to copy the next system, open the station on Spansh, and plot the route (copy for the galaxy map; we can't plot it in game).
  - **Loop routes** (A → B → A) as a quick option: the most-asked trading question.
- [ ] **Sell my cargo:** take what's in the hold right now from `Cargo.json`, and find the best place to sell each commodity near here, with price, demand, distance, pad size and price age. Reuse the `commodity/sell` endpoint.
- [ ] **Find a commodity:** where to buy it or sell it near a system, searching any commodity by name.
- [ ] **This station:** when docked, the station's market from Spansh, plus "what here is worth buying for a route", which seeds the route planner from here.

## 3. Following a route

- [ ] **Route progress:** the planner remembers the chosen route and ticks hops off live from the journal: `MarketBuy` at the right station, then `Docked` and `MarketSell` at the next. It shows "next: sell 720 t Gold at …".
- [ ] **Trade overlay**, optional: the next hop, what to buy or sell, and the expected profit. Its options go in Overlay Studio only (see the Studio vs Settings split).
- [ ] **Re-check before buying:** when you dock at a hop's station, refresh that station's prices from Spansh, and warn if they've moved since the route was planned.

## 4. Your trades: the journal profit log

This is your own history, not a price database.

- [ ] From `MarketBuy` and `MarketSell` events, pair each purchase with its sale per commodity to get profit per trade, per run and per hour, and the best commodities and routes you've flown.
- [ ] Optional: a trade report per session to copy, in the style of the BGS Discord report.

## 5. Finishing

- [ ] Tests with fixtures:
  - the parsers for each Spansh reply
  - the form pre-fill from journal state
  - route progress driven by journal events
  - the profit-log pairing
  - "no traffic in replay"
- [ ] An end-to-end run against live Spansh with the real journal, like the BGS one.
- [ ] Add Spansh to the README's integrations list ("only when you ask for a search" already covers it; check the wording).
- [ ] Mini-readme entry; the version is the user's call.

## Not using

- **Inara:** no public trade-search API, and scraping isn't allowed.
- **EDSM:** only one station's market at a time, with no search.
- **Ardent Insight:** an open EDDN-based API. It may be worth a look later as a second source for single-commodity searches, not routes.
