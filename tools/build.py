import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from voidcompass.core.version import APP_VERSION
from tools.version_sync import validate_version_sync

# This script automates the build process for SurveyAnalysis

if __name__ == '__main__':
    if sys.platform != 'win32':
        raise SystemExit(
            "Void Compass 5.3.9 and newer require Windows x64/WebView2. "
            "The experimental Linux build has been retired."
        )
    # Resolve dependencies and build paths relative to this script, even when
    # invoked from another directory. Bootstrap before importing packages that
    # may not yet be installed in this Python environment.
    project_dir = PROJECT_ROOT
    os.chdir(project_dir)
    version_errors = validate_version_sync(project_dir)
    if version_errors:
        raise SystemExit(
            "Release version metadata is out of sync with "
            f"src/voidcompass/core/version.py ({APP_VERSION}):\n- "
            + "\n- ".join(version_errors)
            + "\nRun: python tools/version_sync.py --write"
        )
    print(f"Installing build requirements with {sys.executable}...", flush=True)
    try:
        subprocess.run(
            [sys.executable, '-m', 'pip', 'install', '-r',
             str(project_dir / 'requirements.txt')],
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(
            f"Requirements installation failed; build stopped: {exc}"
        ) from exc
    importlib.invalidate_caches()
    import PyInstaller.__main__
    import PyInstaller
    from voidcompass.mining.mining_data import MiningDataStore
    from tools.release_packager import create_release, validate_runtime_images

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

    runtime_images = validate_runtime_images(project_dir)
    print(f"Release preflight passed: {len(runtime_images)} runtime image files validated")

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
        version_info_path = project_dir / 'build' / 'version_info.txt'
        version_info_path.parent.mkdir(parents=True, exist_ok=True)
        with version_info_path.open('w', encoding='utf-8') as f:
            f.write(version_content)

    mining_db_path = os.path.abspath("data/mining_data.db")
    if not os.path.exists(mining_db_path):
        MiningDataStore(mining_db_path)
        print("Created mining_data.db")

    data_sep = os.pathsep
    opts = [
        str(project_dir / 'VoidCompass.py'),  # Main entry point
        '--name=VoidCompass',      # Name of the executable
        '--onefile',               # Bundle everything into one native executable
        '--windowed',              # Hide the console (GUI only)
        '--clean',                 # Clean cache before building
        '--log-level=INFO',
        # Python owns application state; WebView2 owns all UI windows.
        # Exclude Tk and Pillow's optional Tk adapters so PyInstaller cannot
        # pull Tcl/Tk libraries into the executable through dependency hooks.
        '--exclude-module=tkinter',
        '--exclude-module=_tkinter',
        '--exclude-module=PIL.ImageTk',
        '--exclude-module=PIL._tkinter_finder',
        f'--paths={SRC_ROOT}',
        f'--workpath={project_dir / "build"}',
        f'--specpath={project_dir / "build"}',
        f'--distpath={project_dir / "dist"}',
        f'--add-data={project_dir / "assets" / "icons"}{data_sep}assets/icons',
        f'--add-data={project_dir / "assets" / "images"}{data_sep}assets/images',
        f'--add-data={project_dir / "web"}{data_sep}web',
        f'--add-data={project_dir / "data" / "mining_data.db"}{data_sep}data',
        f'--add-data={project_dir / "data" / "codexRef.json"}{data_sep}data',
        f'--add-data={project_dir / "data" / "achievements.json"}{data_sep}data',
        f'--add-data={project_dir / "data" / "engineering_companion"}{data_sep}data/engineering_companion',
        f'--add-data={project_dir / "data" / "build_planner"}{data_sep}data/build_planner',
    ]
    if is_windows:
        opts.extend([
            f'--icon={project_dir / "assets" / "icons" / "icon.ico"}',
            f'--version-file={version_info_path}',
        ])

    print(f"Starting {target_name} build process...")
    PyInstaller.__main__.run(opts)
    
    if is_windows and version_info_path.exists():
        version_info_path.unlink()
    
    dist_dir = project_dir / 'dist'
    # Copy mini-readme.md to dist as UPDATE_LOG.md
    if os.path.exists('mini-readme.md'):
        shutil.copy(project_dir / 'mini-readme.md', dist_dir / 'UPDATE_LOG.md')
        print("Copied mini-readme.md to dist/UPDATE_LOG.md")
    if os.path.exists('THIRD_PARTY_NOTICES.md'):
        shutil.copy(
            'THIRD_PARTY_NOTICES.md',
            dist_dir / 'THIRD_PARTY_NOTICES.md',
        )
        print("Copied THIRD_PARTY_NOTICES.md to dist/")
    if os.path.exists(mining_db_path):
        dist_data_dir = project_dir / 'dist' / 'data'
        dist_data_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(mining_db_path, dist_data_dir / 'mining_data.db')
        print("Copied mining_data.db to dist/data/mining_data.db")
    codex_reference_path = project_dir / 'data' / 'codexRef.json'
    if codex_reference_path.exists():
        dist_data_dir = project_dir / 'dist' / 'data'
        dist_data_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(codex_reference_path, dist_data_dir / 'codexRef.json')
        print("Copied codexRef.json to dist/data/codexRef.json")
    images_src = project_dir / 'assets' / 'images'
    if images_src.is_dir():
        images_dest = dist_dir / 'assets' / 'images'
        if images_dest.exists():
            shutil.rmtree(images_dest)
        shutil.copytree(images_src, images_dest)
        print("Copied images to dist/assets/images")
    col_data_src = project_dir / 'colonisation_data.json'
    if col_data_src.exists():
        shutil.copy(col_data_src, dist_dir / 'colonisation_data.json')
        print("Copied colonisation_data.json to dist/")
    mining_sessions_src = project_dir / 'mining_sessions.json'
    if mining_sessions_src.exists():
        shutil.copy(mining_sessions_src, dist_dir / 'mining_sessions.json')
        print("Copied mining_sessions.json to dist/")
    engineer_mats_src = project_dir / 'engineer_materials.json'
    if engineer_mats_src.exists():
        shutil.copy(engineer_mats_src, dist_dir / 'engineer_materials.json')
        print("Copied engineer_materials.json to dist/")

    release = create_release(project_dir, APP_VERSION)
    print(f"Created public release folder: {release['package_dir']}")
    print(f"Created public release archive: {release['archive_path']}")
    print(f"Included runtime images: {release['runtime_image_count']}")
    print(f"Release SHA-256: {release['sha256']}")
    if not release["license_included"]:
        print("Warning: no LICENSE or COPYING file was found to include.")

    print("Build complete. Use 'dist' for testing and 'release' for publishing.")
