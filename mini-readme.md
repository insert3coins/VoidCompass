# VoidCompass // UPDATE LOG

## v4.0.4 // Freeze Diagnostics + Deadlock Fixes
**Release Date:** 2026-Jul-10

### Dashboard Reliability
*   Prevented Profile and BGS pages from blocking Tk while the journal watcher owns the shared database lock.
*   Added cached, non-blocking reads for the EDSM upload queue and BGS system/faction lists.
*   Verified every integrated page can be opened in sequence without creating a persistent Not Responding state.

### Diagnostics
*   Re-enabled automatic crash and UI-freeze reporting by default.
*   Added independent runtime-trace and crash-reporter controls under Settings → Diagnostics.
*   Added automatic thread stack dumps after a sustained UI heartbeat stall and retained the Ctrl+Alt+D manual dump shortcut.
*   Crash logs now start fresh on every application launch to prevent indefinite file growth.

### Version
*   Bumped app version to **4.0.4**.

## v4.0.3 // Themed Native Controls
**Release Date:** 2026-Jul-10

### Interface Controls
*   Reworked page actions around shared primary, standard, muted, and destructive button treatments.
*   Added consistent hover, pressed, disabled, and active-subtab states across the integrated application pages.
*   Replaced native page scrollbars with narrow, square, arrowless controls that use the VoidCompass palette and cyan interaction feedback.
*   Preserved specialised Settings toggles and section navigation while keeping them tied to the shared theme colours.

### Version
*   Bumped app version to **4.0.3**.

## v4.0.2 // Native Commander Console
**Release Date:** 2026-Jul-10

### Unified Native Interface
*   Added a shared native Tk theme and component library based on the VoidCompass commander-console design.
*   Restyled the dashboard and application tools with a consistent palette, typography, cards, controls, notebooks, and data tables.
*   Added the persistent left navigation rail, command strip, holographic card details, active cyan page marker, and an inset application frame.

### Integrated Dashboard Pages
*   Profile, Explore, Trade, Mining, Route, Carrier, Colony, BGS, Engineer, and Settings now open inside the main dashboard workspace.
*   Navigation switches pages without creating additional tool windows and keeps the rail and live command strip visible.
*   Existing page calculations, refresh hooks, and actions remain connected to the live application state.
*   Native HUD and overlay windows remain independent and retain their existing styling and behavior.

### Version
*   Bumped app version to **4.0.2**.

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
