import tkinter as tk
import logging
import os
import sys
from dashboard import MainDashboard

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

if __name__ == "__main__":
    root = tk.Tk()
    
    # Attempt to set the window icon
    try:
        root.iconbitmap(resource_path("icon.ico"))
    except Exception:
        pass # Icon file likely missing or invalid

    app = MainDashboard(root)
    root.mainloop()