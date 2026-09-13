"""Shared overlay position serialization."""

def position_geometry(x, y, width=None, height=None):
    """Build an absolute window geometry string for any virtual-screen quadrant.

    ``+{x}+{y}`` produces invalid ``+-120`` fragments for monitors to the
    left or above the primary display.  Explicit signs keep Studio positions
    portable across the complete virtual desktop.
    """
    prefix = ""
    if width is not None and height is not None:
        prefix = f"{max(1, int(width))}x{max(1, int(height))}"
    return f"{prefix}{int(round(float(x))):+d}{int(round(float(y))):+d}"
