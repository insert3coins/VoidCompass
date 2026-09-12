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

To install it, right-click `install.inf` and choose **Install** (under **Show
more options** if needed). Windows may ask for administrator access when it
copies the files into its cursor directory. Then:

1. Press **Win + R**, enter `main.cpl`, and press **Enter**.
2. Open the **Pointers** tab.
3. Choose **Void Compass** from **Scheme**, then click **Apply** and **OK**.

If the Mouse Properties window was already open, close and reopen it after
installing. Older installers assigned the cursor files without adding a named
scheme: rerun the updated installer, or use **Save As… → Void Compass** on the
Pointers tab while the installed Void Compass cursors are shown, then apply.

`generate_theme.py` is the small Pillow-based generator used to rebuild the
cursor files from the in-app artwork and role-specific drawing code. Run
`python mouse/generate_theme.py` from the repository root to regenerate the
static cursors, animations and preview. Reinstall with `install.inf` after
regenerating so the copies in the Windows cursor directory are updated.
