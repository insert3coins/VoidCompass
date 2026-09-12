# Void Compass Windows mouse theme

This folder contains the complete Windows cursor set for Void Compass. The
Windows set uses a slightly deeper cyan and softer amber so it stays in the
same family as the application cursor while remaining easy to distinguish.

The theme covers normal select, help, background work, busy, precision, text,
handwriting, unavailable, all four resize directions, move, alternate select,
link, location, pin, and person pointers. Each cursor is a standard 32 by 32
Windows `.cur` file with its hotspot set for the role.

To install it, right-click `install.inf`, choose **Install**, then open
`VoidCompass.theme` from this folder. Windows may ask for administrator access
when it copies the files into its cursor directory. If the theme does not
refresh immediately, open **Settings → Bluetooth & devices → Mouse → Additional
mouse settings → Pointers**, choose the Void Compass scheme, and apply it.

`generate_theme.py` is the small Pillow-based generator used to rebuild the
cursor files from the in-app artwork.
