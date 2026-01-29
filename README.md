# Elite Dangerous - Survey Analysis Logger

A real-time survey and exploration companion for Elite Dangerous. This tool reads your journal files as you play, providing a tactical overlay, a detailed dashboard, and live integration with EDSM and Discord to track your exploration progress.

![Dashboard Screenshot](https://i.imgur.com/placeholder.png "Dashboard Screenshot")

## Features

*   **Real-time Event Logging:** Reads the Elite Dangerous journal files live to track your actions.
*   **Detailed Dashboard:** A desktop application that provides a central view of:
    *   Current system and coordinates.
    *   System scan progress (bodies scanned vs. total).
    *   Exobiology scan count.
    *   EDSM upload status and queue size.
    *   A detailed console log of all major events.
*   **Tactical HUD Overlay:** A movable, always-on-top window that displays critical information over your game:
    *   Current system and route progress (e.g., "Jump 5 of 20").
    *   Navigation target and distance in light-years.
    *   A visual progress bar for system scans.
    *   Live system traffic data from EDSM (24h, weekly, total).
    *   Organic (biology) scan count.
*   **Live Discord Integration:**
    *   Posts a single, persistent message to a specified webhook that updates in real-time.
    *   Dynamic titles for events like `🚀 JUMP COMPLETE`, `🛰️ SCAN: [Body]`, and `🌱 BIO-LOG: [Genus]`.
    *   Automatically highlights valuable discoveries (Earth-like, Water, Ammonia worlds, and Terraformables) with special emojis and colors.
    *   Resets with a new message upon jumping to a new system.
*   **EDSM Integration:**
    *   Automatically uploads your travel history and scan data (`FSDJump`, `FSSDiscoveryScan`, `Scan`, `ScanOrganic`) to the EDSM database.
    *   Fetches system traffic data to display on the HUD.
*   **Easy Configuration:**
    *   Automatically creates a `config.json` file on first launch.
    *   In-app settings panel to configure all major features.
    *   Saves window positions for a consistent layout.

---

## Installation & Setup

1.  **Prerequisites:**
    *   Python 3.x must be installed.
    *   You will need the `requests` library. You can install it by running:
        ```
        pip install requests
        ```

2.  **Running the Application:**
    *   Download the `SurveyAnalysis.py` script.
    *   Run the script from your terminal:
        ```
        python SurveyAnalysis.py
        ```

3.  **First-Time Configuration:**
    *   On the first run, the application will create a `config.json` file in the same directory.
    *   The application will open. Click the **[ CONFIGURATION ]** button in the top-right corner.
    *   Fill in the required fields in the settings panel.

---

## Configuration

The application can be configured via the in-app settings panel or by directly editing the `config.json` file.

*   `journal_path`: The path to your Elite Dangerous journal files. The application attempts to find the default path, but you may need to adjust it.
    *   *Default:* `C:\Users\[YourUser]\Saved Games\Frontier Developments\Elite Dangerous`

*   `edsm_cmdr_name`: Your in-game commander name as registered on EDSM.

*   `edsm_api_key`: Your personal API key from your EDSM profile settings.

*   `discord_webhook`: The full URL for the Discord webhook you want the bot to post updates to.

*   `overlay_enabled`: Set to `true` to show the tactical HUD overlay, or `false` to hide it.

*   `hud_x` / `hud_y`: The screen coordinates for the HUD's position. This is set automatically when you move the HUD.

*   `main_geometry` / `settings_geometry`: The size and position of the main dashboard and settings windows. These are saved automatically when you close the windows.

**Note:** After saving changes in the configuration window, a restart of the application is recommended for all changes to take effect.

---

## Usage

*   **Start the application before or during your game session.** It will automatically detect the latest journal file and start processing events.
*   **The Dashboard** provides a comprehensive overview and a log of all activities.
*   **The HUD** can be clicked and dragged to any position on your screen. Its position will be saved for the next session.
*   **Discord messages** will be created/updated automatically in the channel associated with your webhook URL. A new message is created each time you jump to a new system.

Happy exploring, Commander! o7