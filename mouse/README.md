# Void Compass Windows mouse theme

This folder contains the complete Windows cursor set for Void Compass. The
Windows set uses a slightly deeper cyan and softer amber so it stays in the
same family as the application cursor while remaining easy to distinguish.

The theme covers normal select, help, background work, busy, precision, text,
handwriting, unavailable, all four resize directions, move, alternate select,
link, location, pin, and person pointers. Pointers are 32 by 32 pixels with a tight dark outline for contrast on light
and dark backgrounds. Busy and working-in-background use 12-frame animated
`.ani` files; `.cur` versions are included as static alternatives. The remaining
roles use standard Windows `.cur` files, with hotspots set for their shapes.

[Preview all cursor shapes](preview.png). The preview shows each role enlarged
and at native size on both light and dark backgrounds. Busy and working are
shown as still frames; the installed `.ani` versions rotate.

To install it, right-click `install.inf`, choose **Install**, then open
`VoidCompass.theme` from this folder. Windows may ask for administrator access
when it copies the files into its cursor directory. If the theme does not
refresh immediately, open **Settings → Bluetooth & devices → Mouse → Additional
mouse settings → Pointers**, choose the Void Compass scheme, and apply it.

`generate_theme.py` is the small Pillow-based generator used to rebuild the
cursor files from the in-app artwork and role-specific drawing code. Run
`python mouse/generate_theme.py` from the repository root to regenerate the
static cursors, animations and preview. Reinstall with `install.inf` after
regenerating so the copies in the Windows cursor directory are updated.
