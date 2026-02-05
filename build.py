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
        StringStruct(u'FileDescription', u'Elite Dangerous Exploration & Navigation Tool'),
        StringStruct(u'FileVersion', u'{v_str}'),
        StringStruct(u'InternalName', u'VoidCompass'),
        StringStruct(u'LegalCopyright', u'Copyright (c) 2026 insert3coins'),
        StringStruct(u'OriginalFilename', u'VoidCompass.exe'),
        StringStruct(u'ProductName', u'Void Compass'),
        StringStruct(u'ProductVersion', u'{v_str}')])
      ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"""
    with open('version_info.txt', 'w', encoding='utf-8') as f:
        f.write(version_content)

    opts = [
        'VoidCompass.py',          # Your main entry point
        '--name=VoidCompass',      # Name of the executable
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
    
    dist_dir = os.path.join(os.getcwd(), 'dist')
    # Copy mini-readme.md to dist as UPDATE_LOG.md
    if os.path.exists('mini-readme.md'):
        shutil.copy('mini-readme.md', os.path.join(dist_dir, 'UPDATE_LOG.md'))
        print("📄 Copied mini-readme.md to dist/UPDATE_LOG.txt")

    print("✅ Build Complete. Check the 'dist' folder.")
