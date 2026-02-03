import PyInstaller.__main__
import os
import shutil
from version import APP_VERSION

# This script automates the build process for SurveyAnalysis

if __name__ == '__main__':
    # Clean up previous build artifacts
    if os.path.exists('build'):
        print("🧹 Removing previous build folder...")
        shutil.rmtree('build')

    # Convert "1.3.0" -> (1, 3, 0, 0) for Windows Version Info
    v_parts = [int(x) for x in APP_VERSION.split('.')]
    while len(v_parts) < 4:
        v_parts.append(0)
    v_tuple = tuple(v_parts)
    v_str = f"{v_parts[0]}.{v_parts[1]}.{v_parts[2]}.{v_parts[3]}"

    # Create version info file for Windows executable details
    version_content = f"""
# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={v_tuple},
    prodvers={v_tuple},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'insert3coins'),
        StringStruct(u'FileDescription', u'Elite Dangerous Survey Analysis Tool'),
        StringStruct(u'FileVersion', u'{v_str}'),
        StringStruct(u'InternalName', u'SurveyAnalysis'),
        StringStruct(u'LegalCopyright', u'Copyright (c) 2026 insert3coins'),
        StringStruct(u'OriginalFilename', u'SurveyAnalysis.exe'),
        StringStruct(u'ProductName', u'Survey Analysis'),
        StringStruct(u'ProductVersion', u'{v_str}')])
      ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"""
    with open('version_info.txt', 'w', encoding='utf-8') as f:
        f.write(version_content)

    opts = [
        'SurveyAnalysis.py',       # Your main entry point
        '--name=SurveyAnalysis',   # Name of the executable
        '--onefile',               # Bundle everything into a single .exe file
        '--windowed',              # Hide the console (GUI only)
        '--clean',                 # Clean cache before building
        '--log-level=INFO',
        '--icon=icon.ico',         # Sets the file icon for the .exe
        '--add-data=icon.ico;.',   # Bundles the icon inside the .exe for the GUI
        '--version-file=version_info.txt'
    ]

    print("🚀 Starting Build Process...")
    PyInstaller.__main__.run(opts)
    
    if os.path.exists('version_info.txt'):
        os.remove('version_info.txt')
    
    # --- Create Distribution README ---
    readme_content = f"""SURVEY ANALYSIS // ELITE DANGEROUS COMPANION // v{APP_VERSION}
============================================

DESCRIPTION
-----------
Survey Analysis is a real-time exploration companion for Elite Dangerous.
It reads your journal files as you play to provide:
- A tactical HUD overlay with navigation and scan progress.
- A Cargo Manifest overlay to track inventory.
- A Route Planner for custom navigation.
- Automatic Screenshot conversion (BMP -> PNG).
- Automatic data upload to EDSM.
- Live telemetry updates to Discord.

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

4. Screenshots (Optional):
   - Enable the converter in Settings.
   - Point it to your Elite Dangerous screenshot folder.
   - It will auto-convert BMPs to PNGs and rename them with the system name.

USAGE
-----
- Launch the app before or during your game session.
- The "Tactical Overlay" and "Cargo Overlay" can be dragged anywhere on screen.
- Use the [ ROUTE PLANNER ] to plot custom waypoints.
- Data is automatically uploaded to EDSM and Discord as you play.
- The window position is saved automatically upon exit.

Fly Safe, Commander! o7
"""

    dist_dir = os.path.join(os.getcwd(), 'dist')
    readme_path = os.path.join(dist_dir, 'README.md')
    
    if os.path.exists(dist_dir):
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(readme_content)
        print(f"📄 README.txt created at: {readme_path}")

    # Copy mini-readme.md to dist as UPDATE_LOG.md
    if os.path.exists('mini-readme.md'):
        shutil.copy('mini-readme.md', os.path.join(dist_dir, 'UPDATE_LOG.md'))
        print("📄 Copied mini-readme.md to dist/UPDATE_LOG.txt")

    print("✅ Build Complete. Check the 'dist' folder.")