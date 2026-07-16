"""Source-tree worker entry point for full market database builds.

The user-facing controls live in Trade > Database. Development runs launch this
module in a separate Python process; packaged runs use the equivalent worker
mode built into VoidCompass.exe. Either path keeps the multi-gigabyte import
away from the native dashboard process.
"""

import sys
import tkinter as tk
from tkinter import messagebox

from trade import seed


def main():
    if "--trade-seed-worker" in sys.argv:
        raise SystemExit(seed.run_worker(sys.argv[1:]))

    # A direct double-click should explain where the integrated controls moved
    # rather than opening a second, duplicate database-management surface.
    root = tk.Tk()
    root.withdraw()
    messagebox.showinfo(
        "Void Compass Market Database",
        "Market database controls are integrated into Void Compass.\n\n"
        "Open TRADE, then select DATABASE.",
        parent=root,
    )
    root.destroy()


if __name__ == "__main__":
    main()
