# TODO: Trading

## Next: trade routes from a whole system

Today the route planner starts from one station. Commanders want to give just a system and find the best route from **any station in it**.

Spansh's trade router only starts from a station, so a system search means trying the stations there and comparing the results. One request makes this cheap: `GET /api/dump/<system id64>` returns **every station's market in the system**. For Sol, that's 10 orbital stations, each with its full commodity list.

### How it works

- [ ] **A "From any station in this system" switch** on the route planner. With it on, the station field is optional; you give a system, and the rest of the form stays the same.
- [ ] **Fetch the system's markets once:** `spansh.system_dump(id64)` (new), with the system's id64 coming from `/api/search/systems`, as `system_stations()` already finds it. Cache it for the session, like the station lists.
  - **Check first:** the dump's top-level `stations` held the 10 orbital stations for Sol. Surface ports and settlements seem to be under `bodies`. Find where they are and include them when "Planetary ports" is ticked.
  - The dump uses different field names from the station endpoint: `landingPads`, `distanceToArrival`, and `market.commodities` with its own keys. Parse it into the same shape as `market.parse_station`, against a saved fixture.
- [ ] **Drop the stations the settings rule out:**
  - no large pad when "Large pad" is ticked
  - fleet carriers, unless "Fleet carriers" is ticked
  - planetary ports, unless ticked
  - no market, or nothing in stock
  - prices older than the "prices no older than" setting
- [ ] **Pick the most promising stations to try**, by the number of commodities in stock and how fresh the market is. This is a sensible guess, not a guarantee, and the results say which stations were tried.
- [ ] **Run the trade router from the top 3 at the same time**, as three Spansh jobs in parallel. That takes about as long as one search, not three times as long.
  - An option goes up to 6 ("Try more stations: slower and heavier on Spansh").
  - **Never every station.** Sol has 63 stations with markets, which would be 63 jobs on a volunteer's service.
- [ ] **Progress:** one line per station in the existing progress panel, each with its own state (queued, started, done, failed) and the shared timer. **Stop** stops all of them.
- [ ] **Results:** a comparison at the top ("Best start in Sol: Daedalus 31M · Abraham Lincoln 28M · Mars High 22M").
  - Each route opens to the usual hop cards.
  - **Follow this route** works on any of them.
  - **Loop these two** still works on any hop.
  - A station that found no profitable route says so rather than disappearing.
- [ ] **Cache** the whole system search like single searches, keyed on the system and the settings.

### Also

- [ ] **Find commodity and Sell cargo by system:** use the same dump to say what the system's own stations pay or charge, beside Spansh's nearby search. "In Sol: Abraham Lincoln pays 9,800" matters when you're already there.
- [ ] The **Market** view can show any station in the system from the dump, with a station picker.

### Finishing

- [ ] Tests:
  - the dump parser, against a trimmed fixture of the real Sol dump
  - station filtering for pad, carriers, planetary and age
  - the ranking
  - the parallel searches, including stopping them and one of them failing
  - the comparison view data
- [ ] An end-to-end run against live Spansh: Sol, then a quieter system, with screenshots of the progress and the comparison.
- [ ] Mini-readme entry; the version is the user's call (5.5.2.6 isn't committed yet, or 5.5.2.7).

## Done in 5.5.2.6

Kept for reference: what the Trading tab already does, and what we learned building it.

- **The tab:**
  - Overview with charts: profit per day, running total, best commodities, routes flown.
  - Route planner, with loop routes and following a route live from the journal (with price rechecks on docking).
  - Sell cargo, find commodity, market (from the game's Market.json when docked, or Spansh), and history (sessions, profit per hour, Discord report).
- **The Trade Route overlay:** the next step of the followed route.
- **Your own trades in `trading.db`:** profit is exact from `MarketSell.AvgPricePaid`, and a value of 0 means a sale with no cost (mined or salvaged), kept apart from trading.
- **Station names are matched to Spansh's spelling** before planning. Something that isn't a station there, like a station type ("Orbis Starport"), gets a picker with the system's stations instead of an error.
- **The route progress panel:** steps, a timer and Stop. Spansh only reports queued, started and done. The default is 3 hops, about 45 s; 4 hops took about 106 s.

### Spansh, as it really is

Read from spansh.co.uk's own JavaScript.

- **Trade router:** `POST /api/trade/route`, then poll `/api/results/<job>`.
  - Fields: `system`, `station`, `starting_capital`, `max_cargo`, `max_hop_distance`, `max_hops`, `max_system_distance`, `max_price_age`, `requires_large_pad`, `allow_planetary`, `allow_player_owned`, `allow_prohibited`, `allow_restricted_access`, `permit`, `unique`.
  - **`max_price_age` is in seconds.**
  - It has no loop option, so loops are worked out from both stations' markets.
- **Commodity searches:** `GET /api/commodity/{buy|sell}/{system}/{name}/{amount}`. The reply holds stations with their whole markets, nearest first. It's large, so only keep what's needed.
- **One station:** `GET /api/station/<market id>`. **A system's stations:** `/api/search/systems?q=`, then `/api/system/<id64>`.
- **Commodity names:** Spansh only matches its exact English names, which are case-sensitive. The full list comes from `/api/stations/field_values/market`; see `trading/commodities.py` for Frontier's quirky symbols. The EDCD FDevIDs commodity list has no licence, so never ship it.
- **Don't show Spansh's galaxy-wide highest prices** as a target: outliers make them misleading.

## Not using

- **Inara:** no public trade-search API, and scraping isn't allowed.
- **EDSM:** only one station's market at a time, with no search.
- **Ardent Insight:** an open EDDN-based API. It may be worth a look later as a second source for single-commodity searches, not routes.
