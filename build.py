import PyInstaller.__main__
import PyInstaller
import importlib.util
import os
import shutil
import sys
from version import APP_VERSION
from mining_data import MiningDataStore
from release_packager import create_release

# This script automates the build process for SurveyAnalysis

if __name__ == '__main__':
    if sys.platform != 'win32':
        raise SystemExit(
            "Void Compass 5.3.9 and newer require Windows x64/WebView2. "
            "The experimental Linux build has been retired."
        )
    is_windows = True
    target_name = "Windows-x64"
    pyinstaller_version = tuple(
        int(part) for part in PyInstaller.__version__.split('.')[:3]
    )
    if pyinstaller_version < (6, 21, 0):
        raise SystemExit(
            "PyInstaller 6.21.0 or newer is required. Older Windows one-file "
            "bootloaders can leak VCRUNTIME DLLs and leave _MEI directories behind. "
            "Run: python -m pip install -U 'pyinstaller>=6.21.0'"
        )
    if importlib.util.find_spec("webview") is None:
        raise SystemExit(
            "pywebview is required for the HTML command deck and cockpit overlays. "
            "Run: python -m pip install -r requirements.txt"
        )
    print(f"Building with PyInstaller {PyInstaller.__version__}")

    # Clean up previous build artifacts
    if os.path.exists('build'):
        print("Removing previous build folder...")
        shutil.rmtree('build')
    # Windows PE version fields accept exactly four numeric components. Keep
    # the complete application version in the descriptive string fields while
    # safely truncating only the fixed numeric tuple for hotfix versions such
    # as 5.4.2.2.1.
    v_parts = [int(x) for x in APP_VERSION.split('.')]
    v_tuple = tuple((v_parts + [0, 0, 0, 0])[:4])
    v_str = APP_VERSION

    # Create PE metadata only for the Windows build.
    if is_windows:
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

    mining_db_path = os.path.abspath("mining_data.db")
    if not os.path.exists(mining_db_path):
        MiningDataStore(mining_db_path)
        print("Created mining_data.db")

    data_sep = os.pathsep
    opts = [
        'VoidCompass.py',          # Your main entry point
        '--name=VoidCompass',      # Name of the executable
        '--onefile',               # Bundle everything into one native executable
        '--windowed',              # Hide the console (GUI only)
        '--clean',                 # Clean cache before building
        '--log-level=INFO',
        f'--add-data=icon.ico{data_sep}.',
        f'--add-data=icon-source.png{data_sep}.',
        f'--add-data=Images{data_sep}Images',
        f'--add-data=web{data_sep}web',
        f'--add-data=mining_data.db{data_sep}.',
        f'--add-data=codexRef.json{data_sep}.',
        f'--add-data=data/achievements.json{data_sep}data',
    ]
    if is_windows:
        opts.extend([
            '--icon=icon.ico',
            '--version-file=version_info.txt',
        ])

    print(f"Starting {target_name} build process...")
    PyInstaller.__main__.run(opts)
    
    if os.path.exists('version_info.txt'):
        os.remove('version_info.txt')
    
    dist_dir = os.path.join(os.getcwd(), 'dist')
    # Copy mini-readme.md to dist as UPDATE_LOG.md
    if os.path.exists('mini-readme.md'):
        shutil.copy('mini-readme.md', os.path.join(dist_dir, 'UPDATE_LOG.md'))
        print("Copied mini-readme.md to dist/UPDATE_LOG.md")
    if os.path.exists('THIRD_PARTY_NOTICES.md'):
        shutil.copy(
            'THIRD_PARTY_NOTICES.md',
            os.path.join(dist_dir, 'THIRD_PARTY_NOTICES.md'),
        )
        print("Copied THIRD_PARTY_NOTICES.md to dist/")
    if os.path.exists(mining_db_path):
        shutil.copy(mining_db_path, os.path.join(dist_dir, 'mining_data.db'))
        print("Copied mining_data.db to dist/mining_data.db")
    if os.path.exists('codexRef.json'):
        shutil.copy('codexRef.json', os.path.join(dist_dir, 'codexRef.json'))
        print("Copied codexRef.json to dist/codexRef.json")
    images_src = os.path.join(os.getcwd(), 'Images')
    if os.path.isdir(images_src):
        images_dest = os.path.join(dist_dir, 'Images')
        if os.path.exists(images_dest):
            shutil.rmtree(images_dest)
        shutil.copytree(images_src, images_dest)
        print("Copied Images to dist/Images")
    col_data_src = os.path.join(os.getcwd(), 'colonisation_data.json')
    if os.path.exists(col_data_src):
        shutil.copy(col_data_src, os.path.join(dist_dir, 'colonisation_data.json'))
        print("Copied colonisation_data.json to dist/")
    mining_sessions_src = os.path.join(os.getcwd(), 'mining_sessions.json')
    if os.path.exists(mining_sessions_src):
        shutil.copy(mining_sessions_src, os.path.join(dist_dir, 'mining_sessions.json'))
        print("Copied mining_sessions.json to dist/")
    engineer_mats_src = os.path.join(os.getcwd(), 'engineer_materials.json')
    if os.path.exists(engineer_mats_src):
        shutil.copy(engineer_mats_src, os.path.join(dist_dir, 'engineer_materials.json'))
        print("Copied engineer_materials.json to dist/")

    release = create_release(os.getcwd(), APP_VERSION)
    print(f"Created public release folder: {release['package_dir']}")
    print(f"Created public release archive: {release['archive_path']}")
    print(f"Included runtime images: {release['runtime_image_count']}")
    print(f"Release SHA-256: {release['sha256']}")
    if not release["license_included"]:
        print("Warning: no LICENSE or COPYING file was found to include.")

    print("Build complete. Use 'dist' for testing and 'release' for publishing.")
