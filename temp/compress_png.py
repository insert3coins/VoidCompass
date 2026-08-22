"""
compress_png.py
---------------
Optimise PNG artwork for runtime use while preserving transparency.

Strategy (in order):
  1. (Optional) Remove the background only when --remove-bg is explicitly set
  2. (Optional) Trim unused transparent canvas while retaining safe padding
  3. Resize oversized artwork to the maximum dimension (default: 512px)
  4. Pillow lossless optimisation (level 9)
  5. Optionally quantize when --quantize is explicitly set
  6. Scale down further only when still above the requested file-size limit

Usage:
    python compress_png.py                        # all PNGs in current folder
    python compress_png.py image.png              # single file
    python compress_png.py folder/                # all PNGs in a folder
    python compress_png.py *.png -o out/          # custom output folder
    python compress_png.py image.png --remove-bg  # remove background first
    python compress_png.py Images/ships --overwrite --backup-dir art_sources/ships

Options:
    --output     / -o   Output directory (default: creates a "compressed/" subfolder)
    --limit              Size limit in KB (default: 900)
    --overwrite          Replace runtime copies after optimisation
    --backup-dir         Preserve originals here before overwriting
    --max-size           Maximum pixel dimension (default: 512)
    --remove-bg          Explicitly remove the background
    --trim-alpha         Trim unused transparent canvas around the artwork
    --trim-padding       Transparent padding retained by --trim-alpha (default: 10px)
    --quantize           Permit 256-colour reduction if lossless output is too large

Requirements:
    pip install pillow
    pip install rembg onnxruntime   (only needed for background removal)
"""

import sys
import argparse
import io
import shutil
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("ERROR: Pillow is not installed. Run: pip install pillow")
    sys.exit(1)


# ── Background removal ────────────────────────────────────────────────────────

def remove_background(img: Image.Image) -> Image.Image:
    """Remove background using rembg (AI-based, U2Net model)."""
    try:
        from rembg import remove
    except ImportError:
        print("  ERROR: rembg not installed. Run: pip install rembg onnxruntime")
        sys.exit(1)

    # rembg works on bytes
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    result_bytes = remove(buf.read())
    return Image.open(io.BytesIO(result_bytes)).convert("RGBA")


# ── Quantize with alpha ───────────────────────────────────────────────────────

def quantize_with_alpha(img: Image.Image, colors: int = 256) -> Image.Image:
    """
    Quantize RGBA image while preserving the alpha channel.
    Pillow's quantize() drops alpha, so we split it out, quantize RGB only,
    then paste the original alpha back in.
    """
    r, g, b, a = img.split()
    rgb = Image.merge("RGB", (r, g, b))
    rgb_q = rgb.quantize(colors=colors, method=Image.Quantize.MEDIANCUT)
    result = rgb_q.convert("RGBA")
    result.putalpha(a)
    return result


# ── PNG encode ────────────────────────────────────────────────────────────────

def png_bytes(img: Image.Image, compress_level: int = 9) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True, compress_level=compress_level)
    return buf.getvalue()


# ── Core pipeline ─────────────────────────────────────────────────────────────

def _fit_within(img: Image.Image, max_dim: int) -> tuple[Image.Image, bool]:
    """Return a high-quality copy no larger than max_dim on either axis."""
    width, height = img.size
    if max_dim <= 0 or max(width, height) <= max_dim:
        return img, False
    ratio = max_dim / max(width, height)
    size = (max(1, round(width * ratio)), max(1, round(height * ratio)))
    return img.resize(size, Image.Resampling.LANCZOS), True


def _trim_alpha(img: Image.Image, padding: int) -> tuple[Image.Image, bool]:
    """Crop unused transparent canvas without clipping anti-aliased artwork."""
    alpha = img.getchannel("A")
    bbox = alpha.getbbox()
    if not bbox:
        return img, False
    pad = max(0, int(padding or 0))
    left = max(0, bbox[0] - pad)
    top = max(0, bbox[1] - pad)
    right = min(img.width, bbox[2] + pad)
    bottom = min(img.height, bbox[3] + pad)
    crop = (left, top, right, bottom)
    if crop == (0, 0, img.width, img.height):
        return img, False
    return img.crop(crop), True


def compress_to_limit(src: Path, dst: Path, limit_bytes: int, max_dim: int,
                      do_remove_bg: bool, allow_quantize: bool = False,
                      trim_alpha: bool = False, trim_padding: int = 10) -> dict:
    with Image.open(src) as img:
        img.load()
        original_size = src.stat().st_size
        bg_removed = False

        # ── Background removal ────────────────────────────────────────────────
        if do_remove_bg:
            print(f"    removing background (AI)...")
            img = remove_background(img)
            bg_removed = True
        img = img.convert("RGBA")

        trimmed = False
        if trim_alpha:
            img, trimmed = _trim_alpha(img, trim_padding)

        # Resize before checking the encoded byte count. Runtime art should not
        # retain a 1500px transparent canvas simply because its PNG is already
        # below an arbitrary upload limit.
        img, resized = _fit_within(img, max_dim)
        trim_note = "trimmed canvas + " if trimmed else ""
        resize_note = f"resized to {img.width}x{img.height} + " if resized else ""

        # ── Step 1: lossless ──────────────────────────────────────────────────
        data = png_bytes(img, compress_level=9)
        method = (("bg removed + " if bg_removed else "")
                  + trim_note + resize_note + "lossless")

        if len(data) <= limit_bytes:
            _write(dst, data)
            return _result(src.name, original_size, data, method, img.size)

        # ── Step 2: optional quantize ─────────────────────────────────────────
        if allow_quantize:
            quantized = quantize_with_alpha(img, colors=256)
            data = png_bytes(quantized)
            method = (("bg removed + " if bg_removed else "")
                      + trim_note + resize_note + "quantized (256 colours)")

            if len(data) <= limit_bytes:
                _write(dst, data)
                return _result(src.name, original_size, data, method, img.size)

        # ── Step 3: scale down ────────────────────────────────────────────────
        scale_step = 0.85
        min_dim = 64
        work = img.copy()

        for attempt in range(20):
            w, h = work.size

            new_w = max(min_dim, int(w * scale_step))
            new_h = max(min_dim, int(h * scale_step))

            if new_w == w and new_h == h:
                break

            work = work.resize((new_w, new_h), Image.Resampling.LANCZOS)
            pfx = (("bg removed + " if bg_removed else "") + trim_note)

            data = png_bytes(work, compress_level=9)
            method = pfx + f"scaled to {new_w}x{new_h}"
            if len(data) <= limit_bytes:
                _write(dst, data)
                return _result(src.name, original_size, data, method, (new_w, new_h))

            if allow_quantize:
                q = quantize_with_alpha(work, colors=256)
                data = png_bytes(q)
                method = pfx + f"scaled to {new_w}x{new_h} + quantized"
                if len(data) <= limit_bytes:
                    _write(dst, data)
                    return _result(src.name, original_size, data, method, (new_w, new_h))

        _write(dst, data)
        return _result(src.name, original_size, data, method + " WARNING still over limit", work.size)


def _write(dst: Path, data: bytes):
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(data)


def _result(name, orig, data, method, size):
    comp = len(data)
    savings = orig - comp
    pct = (savings / orig * 100) if orig else 0
    return {"file": name, "original": orig, "compressed": comp,
            "savings": savings, "pct": pct, "method": method, "size": size}


# ── Utilities ─────────────────────────────────────────────────────────────────

def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


def collect_pngs(paths: list) -> list:
    result = []
    for p in paths:
        path = Path(p)
        if path.is_dir():
            result.extend(sorted(path.glob("*.png")))
        elif path.suffix.lower() == ".png" and path.exists():
            result.append(path)
        else:
            parent = path.parent or Path(".")
            result.extend(sorted(parent.glob(path.name)))
    return list(dict.fromkeys(result))


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Optimise transparent PNG artwork for compact runtime use."
    )
    parser.add_argument("inputs", nargs="*", default=["."])
    parser.add_argument("--output", "-o", default=None)
    parser.add_argument("--limit", type=int, default=900,
                        help="Size limit in KB (default: 900)")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--backup-dir", default=None,
                        help="Copy originals here before overwriting")
    parser.add_argument("--max-size", type=int, default=512,
                        help="Maximum pixel dimension (default: 512)")
    parser.add_argument("--remove-bg", action="store_true",
                        help="Force background removal on all images")
    parser.add_argument("--trim-alpha", action="store_true",
                        help="Trim unused transparent canvas around artwork")
    parser.add_argument("--trim-padding", type=int, default=10,
                        help="Transparent padding retained by --trim-alpha (default: 10px)")
    parser.add_argument("--no-remove-bg", action="store_true",
                        help=argparse.SUPPRESS)
    parser.add_argument("--quantize", action="store_true",
                        help="Allow 256-colour reduction if lossless output exceeds the limit")
    args = parser.parse_args()

    limit_bytes = args.limit * 1024
    files = collect_pngs(args.inputs)

    if not files:
        print("No PNG files found.")
        sys.exit(0)

    print(f"\n{'-'*62}")
    print(f"  Runtime PNG Optimiser  |  max: {args.max_size}px / {args.limit} KB")
    print(f"{'-'*62}")
    print(f"  Found {len(files)} PNG(s)\n")

    total_orig = total_comp = 0
    warnings = []

    for src in files:
        if args.overwrite:
            dst = src
        elif args.output:
            dst = Path(args.output) / src.name
        else:
            dst = src.parent / "compressed" / src.name

        if args.overwrite and args.backup_dir:
            backup = Path(args.backup_dir) / src.name
            backup.parent.mkdir(parents=True, exist_ok=True)
            if not backup.exists():
                shutil.copy2(src, backup)

        # Background removal and palette reduction are opt-in; neither is
        # appropriate for the authored Void Compass ship catalogue.
        do_remove_bg = bool(args.remove_bg and not args.no_remove_bg)

        print(f"  Processing: {src.name}")
        r = compress_to_limit(
            src, dst, limit_bytes, args.max_size, do_remove_bg, args.quantize,
            args.trim_alpha, args.trim_padding,
        )
        total_orig += r["original"]
        total_comp += r["compressed"]

        status = "OK" if r["compressed"] <= limit_bytes else "!!"
        arrow = "v" if r["savings"] > 0 else "-"
        print(f"  [{status}] {human_size(r['original'])} -> {human_size(r['compressed'])}"
              f"  ({arrow}{abs(r['pct']):.1f}%)")
        print(f"       method: {r['method']}")
        if dst != src:
            print(f"       saved -> {dst}")
        if "WARNING" in r["method"]:
            warnings.append(r["file"])
        print()

    total_savings = total_orig - total_comp
    total_pct = (total_savings / total_orig * 100) if total_orig else 0

    print(f"{'-'*62}")
    print(f"  Total: {human_size(total_orig)} -> {human_size(total_comp)}"
          f"  (saved {human_size(total_savings)}, {total_pct:.1f}%)")
    if warnings:
        print(f"\n  !! Could not get under limit: {', '.join(warnings)}")
        print(f"     Try --max-size 512 for more aggressive scaling")
    print(f"{'-'*62}\n")


if __name__ == "__main__":
    main()
