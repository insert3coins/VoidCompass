"""Isolated worker entry point for full market database builds.

The user-facing controls live in Trade > Database. Keeping the heavy import in
this companion executable prevents the native dashboard from freezing while a
multi-gigabyte Spansh snapshot is decompressed and indexed.
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
