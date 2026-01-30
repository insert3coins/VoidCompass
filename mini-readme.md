# SURVEY ANALYSIS // UPDATE LOG

## v1.3.0 // TACTICAL OVERHAUL
**Release Date:** 2026-Jan-30

### 🌟 NEW FEATURES
*   **Tactical HUD Overlay:** 
    *   A movable, transparent window that stays on top of the game.
    *   Displays current system, navigation target, distance, and scan progress.
    *   Shows live system traffic (ships passed in last 24h).
*   **Live Discord Telemetry:** 
    *   Updates a single, persistent message in your Discord channel (no more spam).
    *   Real-time updates for Jumps, Scans, and Bio-signals.
    *   Visual indicators for valuable bodies (Earth-likes, Water Worlds, etc.).
*   **Update Checker:** 
    *   Automatically checks GitHub for new releases on startup.
    *   Displays an [ UPDATE AVAILABLE ] button if a new version is found.

### 🔧 CORE CAPABILITIES
*   **Real-Time Logging:** Reads Elite Dangerous journals as they are written.
*   **EDSM Integration:** 
    *   Automatic background upload of flight logs and scan data.
    *   Fetches and displays Commander traffic for the current system.
*   **Exobiology Tracking:** 
    *   Dedicated counter for organic scans in the current system.
*   **Route Navigation:** 
    *   Reads `NavRoute.json` to show jumps remaining to destination.

### 🛠️ IMPROVEMENTS
*   **UI Overhaul:** New dark-themed settings menu with toggle switches.
*   **Stability:** Improved journal polling engine and error handling.
*   **Customization:** Window positions are now saved between sessions.