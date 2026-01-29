import PyInstaller.__main__
import os

# This script automates the build process for SurveyAnalysis

if __name__ == '__main__':
    opts = [
        'SurveyAnalysis.py',       # Your main entry point
        '--name=SurveyAnalysis',   # Name of the executable
        '--onefile',               # Bundle everything into a single .exe file
        '--windowed',              # Hide the console (GUI only)
        '--clean',                 # Clean cache before building
        '--log-level=INFO',
        '--icon=icon.ico',         # Sets the file icon for the .exe
        '--add-data=icon.ico;.'    # Bundles the icon inside the .exe for the GUI
    ]

    print("🚀 Starting Build Process...")
    PyInstaller.__main__.run(opts)
    
    # --- Create Distribution README ---
    readme_content = """SURVEY ANALYSIS // ELITE DANGEROUS COMPANION
============================================

INSTALLATION
------------
1. Place 'SurveyAnalysis.exe' anywhere you like.
2. Run the application.
3. A 'config.json' file will be created automatically in the same folder.

CONFIGURATION
-------------
On the first run, click the [ CONFIGURATION ] button in the top right.

1. Journal Path:
   The app usually auto-detects your Elite Dangerous journal folder.
   If not, point it to: 
   C:\\Users\\[YourName]\\Saved Games\\Frontier Developments\\Elite Dangerous

2. EDSM Integration (Optional but Recommended):
   - Go to https://www.edsm.net/ and log in.
   - Click your profile picture -> "My EDSM Profile".
   - Look for the "Account" tab/section to find your API Key.
   - Enter your Commander Name and API Key in the settings.

3. Discord Integration (Optional):
   - In your Discord server, go to Server Settings -> Integrations -> Webhooks.
   - Create a new Webhook, copy the URL.
   - Paste the URL into the "Discord Webhook" field in the app.

USAGE
-----
- Launch the app before or during your game session.
- The "Tactical Overlay" can be dragged anywhere on screen.
- Data is automatically uploaded to EDSM and Discord as you play.
- The window position is saved automatically upon exit.

Fly Safe, Commander! o7
"""

    dist_dir = os.path.join(os.getcwd(), 'dist')
    readme_path = os.path.join(dist_dir, 'README.txt')
    
    if os.path.exists(dist_dir):
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(readme_content)
        print(f"📄 README.txt created at: {readme_path}")

    print("✅ Build Complete. Check the 'dist' folder.")