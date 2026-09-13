"""Source and PyInstaller entry point for Void Compass."""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


def _dispatch():
    if "--html-overlay-host" in sys.argv:
        from voidcompass.overlays.html_overlay_host import main

        flag_index = sys.argv.index("--html-overlay-host")
        return main(sys.argv[flag_index + 1:])
    if "--html-dashboard-host" in sys.argv:
        from voidcompass.dashboard.html_dashboard_host import main

        flag_index = sys.argv.index("--html-dashboard-host")
        return main(sys.argv[flag_index + 1:])

    from voidcompass.app import main

    return main()


if __name__ == "__main__":
    raise SystemExit(_dispatch())
