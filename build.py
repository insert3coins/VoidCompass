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
    print("✅ Build Complete. Check the 'dist' folder.")