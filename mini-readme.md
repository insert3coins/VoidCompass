# VoidCompass // UPDATE LOG

## v3.9.1 // Navigation HUD Refresh
**Release Date:** 2026-Jul-08

### Navigation HUD
*   Expanded the Navigation HUD into a larger in-flight companion overlay.
*   Added a compact previous/current/next route strip with jump-distance readouts.
*   Added route mode context for game NavRoute, waypoint routes, VoidCompass routes, and no-route state.
*   Added scan, bio, value, cargo, traffic, trade session, docked/station, and commander credit readouts.
*   Added system opportunity badges for states like bio signals, valuable bodies, FSS summaries, traffic, docking, and undiscovered systems.
*   Removed noisy route system-name labels and HUD health text after testing so the overlay stays readable.
*   Commander credit changes now refresh the HUD, with a latest balance-log fallback when live balance is not populated yet.

### Version
*   Bumped app version to **3.9.1**.

## v3.8.6 // Route System Plotter
**Release Date:** 2026-Jul-08

### Route Planner
*   Added a dedicated **System Plotter** tab to the Route window.
*   Added live Spansh neutron-highway plotting with start system, destination, jump range, and efficiency controls.
*   Added copy and import actions so plotted systems can be sent straight into the existing waypoint route manager.
*   System plotter inputs are saved per profile, while the Route window continues to remember its window position and size.
*   Verified the live Spansh route API with a Sol-to-Colonia neutron route job.

### Trade
*   Removed the neutron route panel from the Trade window now that system plotting lives in the Route window.
*   Kept Road to Riches in Trade Guides and let it use the full tab width.

### Version
*   Bumped app version to **3.8.6**.

## v3.8.5 // EDDN Upload Compliance + Status
**Release Date:** 2026-Jul-07

### Trade
*   Hardened EDDN commodity uploads against the live commodity schema.
*   Added game version/build, expansion flags, station metadata, carrier access, and status flags where available.
*   Added EDDN upload success/failure notes to the live event timeline/output area.
*   Kept market upload work asynchronous so journal, cargo, status, and credit updates keep flowing.

### Version
*   Bumped app version to **3.8.5**.
