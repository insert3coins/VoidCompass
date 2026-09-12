"""Generate the Void Compass Windows cursor theme assets.

The application cursor remains in ``web/assets``. This theme uses a slightly
deeper cyan and softer amber so the Windows pointer set feels related to, but
still distinct from, the in-app cursor.
"""

from __future__ import annotations

import colorsys
from pathlib import Path
import struct

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parent
APP_CURSOR = ROOT.parent / "web" / "assets" / "void-compass-cursor.png"
SIZE = 32
SCALE = 4
CYAN = (21, 189, 232, 255)
BLUE = (20, 118, 201, 255)
GOLD = (255, 155, 73, 255)
WHITE = (237, 250, 255, 255)
DARK = (10, 15, 28, 255)
RED = (255, 91, 110, 255)


def pt(x: float, y: float) -> tuple[int, int]:
    return round(x * SCALE), round(y * SCALE)


def pts(values: list[tuple[float, float]]) -> list[tuple[int, int]]:
    return [pt(x, y) for x, y in values]


def box(values: tuple[float, float, float, float]) -> tuple[int, int, int, int]:
    return tuple(round(value * SCALE) for value in values)  # type: ignore[return-value]


def font(size: int) -> ImageFont.FreeTypeFont:
    candidates = (
        Path(r"C:\Windows\Fonts\segoeuib.ttf"),
        Path(r"C:\Windows\Fonts\arialbd.ttf"),
    )
    for candidate in candidates:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size * SCALE)
    return ImageFont.load_default()


def icon_canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGBA", (SIZE * SCALE, SIZE * SCALE), (0, 0, 0, 0))
    return image, ImageDraw.Draw(image)


def finish(image: Image.Image) -> Image.Image:
    # A tight dark keyline survives both light and dark Windows backgrounds.
    # The old broad cyan bloom obscured small symbols at their native size.
    alpha = image.getchannel("A")
    outline = Image.new("RGBA", image.size, DARK)
    outline.putalpha(alpha.filter(ImageFilter.MaxFilter(SCALE + 1)))
    return Image.alpha_composite(outline, image).resize((SIZE, SIZE), Image.Resampling.LANCZOS)


def icon(drawer, *, pointer: bool = False) -> Image.Image:
    image, draw = icon_canvas()
    if pointer:
        image.alpha_composite(normal_cursor().resize(image.size, Image.Resampling.LANCZOS))
    drawer(draw)
    return finish(image)


def normal_cursor() -> Image.Image:
    image = Image.open(APP_CURSOR).convert("RGBA")
    output = []
    for red, green, blue, alpha in [image.getpixel((x, y)) for y in range(image.height) for x in range(image.width)]:
        if alpha < 8:
            output.append((red, green, blue, alpha))
            continue
        hue, saturation, value = colorsys.rgb_to_hsv(red / 255, green / 255, blue / 255)
        hue = (hue + 0.02) % 1.0
        red, green, blue = colorsys.hsv_to_rgb(hue, saturation * 0.94, value * 0.97)
        output.append((round(red * 255), round(green * 255), round(blue * 255), alpha))
    image.putdata(output)
    return image


def help_cursor(draw: ImageDraw.ImageDraw) -> None:
    draw.ellipse(box((19, 18, 30, 29)), fill=DARK, outline=GOLD, width=SCALE)
    draw.text(pt(21.5, 17.5), "?", fill=WHITE, font=font(9))


def background_cursor(draw: ImageDraw.ImageDraw, phase: float = 0) -> None:
    draw.ellipse(box((18, 18, 30, 30)), fill=DARK)
    draw.arc(box((19, 19, 29, 29)), phase + 30, phase + 275, fill=CYAN, width=2 * SCALE)
    draw.arc(box((19, 19, 29, 29)), phase + 275, phase + 325, fill=GOLD, width=2 * SCALE)


def busy_cursor(draw: ImageDraw.ImageDraw, phase: float = 0) -> None:
    # One open ring with an amber leading edge; no target-like centre glyph.
    draw.arc(box((6, 6, 26, 26)), phase + 30, phase + 140, fill=BLUE, width=3 * SCALE)
    draw.arc(box((6, 6, 26, 26)), phase + 140, phase + 275, fill=CYAN, width=3 * SCALE)
    draw.arc(box((6, 6, 26, 26)), phase + 275, phase + 325, fill=GOLD, width=3 * SCALE)


def precision_cursor(draw: ImageDraw.ImageDraw) -> None:
    for start, end in [((16, 3), (16, 12)), ((16, 20), (16, 29)),
                       ((3, 16), (12, 16)), ((20, 16), (29, 16))]:
        draw.line([pt(*start), pt(*end)], fill=WHITE, width=SCALE)
    draw.ellipse(box((9, 9, 23, 23)), outline=CYAN, width=SCALE)
    draw.rectangle(box((15.5, 15.5, 16.5, 16.5)), fill=GOLD)


def text_cursor(draw: ImageDraw.ImageDraw) -> None:
    draw.rectangle(box((14, 4, 18, 28)), fill=DARK)
    draw.rectangle(box((15, 5, 17, 27)), fill=CYAN)
    draw.line([pt(8, 5), pt(24, 5)], fill=WHITE, width=SCALE)
    draw.line([pt(8, 27), pt(24, 27)], fill=WHITE, width=SCALE)


def handwriting_cursor(draw: ImageDraw.ImageDraw) -> None:
    shape = pts([(5, 27), (8, 15), (21, 4), (27, 10), (16, 23)])
    draw.polygon(shape, fill=DARK)
    draw.line(shape + [shape[0]], fill=WHITE, width=2 * SCALE, joint="curve")
    draw.line(pts([(8, 22), (22, 8)]), fill=CYAN, width=2 * SCALE)
    draw.polygon(pts([(5, 27), (9, 24), (8, 28)]), fill=GOLD)


def unavailable_cursor(draw: ImageDraw.ImageDraw) -> None:
    draw.ellipse(box((5, 5, 27, 27)), fill=DARK, outline=RED, width=3 * SCALE)
    draw.line([pt(9, 9), pt(23, 23)], fill=RED, width=3 * SCALE)


def vertical_resize(draw: ImageDraw.ImageDraw) -> None:
    draw.line([pt(16, 3), pt(16, 29)], fill=WHITE, width=2 * SCALE)
    draw.polygon(pts([(16, 2), (10, 9), (22, 9)]), fill=CYAN)
    draw.polygon(pts([(16, 30), (10, 23), (22, 23)]), fill=CYAN)
    draw.ellipse(box((14, 14, 18, 18)), fill=GOLD)


def horizontal_resize(draw: ImageDraw.ImageDraw) -> None:
    draw.line([pt(3, 16), pt(29, 16)], fill=WHITE, width=2 * SCALE)
    draw.polygon(pts([(2, 16), (9, 10), (9, 22)]), fill=CYAN)
    draw.polygon(pts([(30, 16), (23, 10), (23, 22)]), fill=CYAN)
    draw.ellipse(box((14, 14, 18, 18)), fill=GOLD)


def diagonal_resize_one(draw: ImageDraw.ImageDraw) -> None:
    draw.line([pt(4, 4), pt(28, 28)], fill=WHITE, width=2 * SCALE)
    draw.polygon(pts([(3, 3), (12, 5), (5, 12)]), fill=CYAN)
    draw.polygon(pts([(29, 29), (20, 27), (27, 20)]), fill=CYAN)
    draw.ellipse(box((14, 14, 18, 18)), fill=GOLD)


def diagonal_resize_two(draw: ImageDraw.ImageDraw) -> None:
    draw.line([pt(28, 4), pt(4, 28)], fill=WHITE, width=2 * SCALE)
    draw.polygon(pts([(29, 3), (20, 5), (27, 12)]), fill=CYAN)
    draw.polygon(pts([(3, 29), (12, 27), (5, 20)]), fill=CYAN)
    draw.ellipse(box((14, 14, 18, 18)), fill=GOLD)


def move_cursor(draw: ImageDraw.ImageDraw) -> None:
    draw.line([pt(16, 3), pt(16, 29)], fill=WHITE, width=2 * SCALE)
    draw.line([pt(3, 16), pt(29, 16)], fill=WHITE, width=2 * SCALE)
    draw.polygon(pts([(16, 2), (11, 8), (21, 8)]), fill=CYAN)
    draw.polygon(pts([(16, 30), (11, 24), (21, 24)]), fill=CYAN)
    draw.polygon(pts([(2, 16), (8, 11), (8, 21)]), fill=CYAN)
    draw.polygon(pts([(30, 16), (24, 11), (24, 21)]), fill=CYAN)
    draw.ellipse(box((13, 13, 19, 19)), fill=DARK, outline=GOLD, width=SCALE)


def alternate_cursor(draw: ImageDraw.ImageDraw) -> None:
    draw.polygon(pts([(16, 3), (27, 17), (20, 17), (20, 28), (12, 28), (12, 17), (5, 17)]), fill=DARK)
    draw.line(pts([(16, 3), (27, 17), (20, 17), (20, 28), (12, 28), (12, 17), (5, 17), (16, 3)]), fill=WHITE, width=2 * SCALE, joint="curve")
    draw.line(pts([(16, 7), (16, 24)]), fill=CYAN, width=SCALE)


def link_cursor(draw: ImageDraw.ImageDraw) -> None:
    # A single extended index finger, with the hotspot at its tip.
    palm = pts([(12, 16), (12, 5), (13, 3), (15, 3), (16, 5),
                (16, 13), (19, 13), (20, 15), (23, 15), (24, 17),
                (27, 17), (27, 22), (23, 29), (13, 29),
                (7, 21), (6, 18), (8, 16), (10, 17), (12, 20)])
    draw.polygon(palm, fill=DARK)
    draw.line(palm + [palm[0]], fill=WHITE, width=1 * SCALE, joint="curve")
    draw.line(pts([(16, 15), (16, 20)]), fill=CYAN, width=SCALE)
    draw.line(pts([(20, 17), (20, 21)]), fill=CYAN, width=SCALE)
    draw.line(pts([(15, 26), (22, 26)]), fill=GOLD, width=SCALE)


def location_cursor(draw: ImageDraw.ImageDraw) -> None:
    draw.ellipse(box((7, 3, 25, 21)), fill=DARK, outline=WHITE, width=2 * SCALE)
    draw.polygon(pts([(8, 15), (16, 30), (24, 15)]), fill=DARK)
    draw.line(pts([(8, 15), (16, 30), (24, 15)]), fill=WHITE, width=2 * SCALE, joint="curve")
    draw.ellipse(box((12, 8, 20, 16)), fill=CYAN, outline=GOLD, width=SCALE)


def person_cursor(draw: ImageDraw.ImageDraw) -> None:
    draw.ellipse(box((11, 3, 21, 13)), fill=DARK, outline=WHITE, width=2 * SCALE)
    draw.polygon(pts([(5, 29), (7, 20), (12, 16), (20, 16), (25, 20), (27, 29)]), fill=DARK)
    draw.line(pts([(5, 29), (7, 20), (12, 16), (20, 16), (25, 20), (27, 29)]), fill=CYAN, width=2 * SCALE, joint="curve")
    draw.ellipse(box((14, 6, 18, 10)), fill=GOLD)


def pin_cursor(draw: ImageDraw.ImageDraw) -> None:
    # Windows calls its location-select role "Pin". Use the same teardrop.
    location_cursor(draw)


def cur_bytes(image: Image.Image, hotspot: tuple[int, int]) -> bytes:
    image = image.convert("RGBA").resize((SIZE, SIZE), Image.Resampling.LANCZOS)
    pixels = [image.getpixel((x, y)) for y in range(SIZE) for x in range(SIZE)]
    xor = bytearray()
    mask_stride = ((SIZE + 31) // 32) * 4
    and_mask = bytearray(mask_stride * SIZE)
    for y in range(SIZE - 1, -1, -1):
        for x in range(SIZE):
            red, green, blue, alpha = pixels[y * SIZE + x]
            xor.extend((blue, green, red, alpha))
        row = (SIZE - 1 - y) * mask_stride
        for x in range(SIZE):
            if pixels[y * SIZE + x][3] < 8:
                and_mask[row + x // 8] |= 1 << (7 - (x % 8))
    payload = struct.pack(
        "<IiiHHIIiiII", 40, SIZE, SIZE * 2, 1, 32, 0,
        len(xor) + len(and_mask), 0, 0, 0, 0,
    ) + xor + and_mask
    entry = struct.pack(
        "<BBBBHHII", SIZE, SIZE, 0, 0, hotspot[0], hotspot[1], len(payload), 22,
    )
    return struct.pack("<HHH", 0, 2, 1) + entry + payload


def write_cur(image: Image.Image, path: Path, hotspot: tuple[int, int]) -> None:
    path.write_bytes(cur_bytes(image, hotspot))


def write_ani(frames: list[Image.Image], path: Path, hotspot: tuple[int, int]) -> None:
    """Write a sequential RIFF/ACON cursor, 12 frames per second."""
    def chunk(tag: bytes, payload: bytes) -> bytes:
        return tag + struct.pack("<I", len(payload)) + payload + b"\0" * (len(payload) % 2)

    header = struct.pack("<9I", 36, len(frames), len(frames), 0, 0, 0, 0, 5, 1)
    icons = b"".join(chunk(b"icon", cur_bytes(frame, hotspot)) for frame in frames)
    payload = b"ACON" + chunk(b"anih", header) + chunk(b"LIST", b"fram" + icons)
    path.write_bytes(chunk(b"RIFF", payload))


def write_preview(assets: dict) -> None:
    """Show every role at 3x, plus native size on light and dark surfaces."""
    width, cell_height, columns = 1000, 170, 5
    rows = (len(assets) + columns - 1) // columns
    sheet = Image.new("RGB", (width, rows * cell_height + 40), "#19232c")
    draw = ImageDraw.Draw(sheet)
    label_font = font(3)
    draw.text((12, 12), "VOID COMPASS  /  CURSOR PREVIEW  /  3x + native size on light and dark", fill=WHITE, font=label_font)
    for index, (name, (image, hotspot)) in enumerate(sorted(assets.items())):
        x, y = (index % columns) * 200, (index // columns) * cell_height + 40
        draw.text((x + 10, y + 8), name.removesuffix(".cur"), fill=WHITE, font=label_font)
        large = image.resize((96, 96), Image.Resampling.NEAREST)
        sheet.paste(large, (x + 8, y + 34), large)
        draw.rectangle((x + 118, y + 33, x + 170, y + 85), fill="#eeeeee")
        sheet.paste(image, (x + 128, y + 43), image)
        sheet.paste(image, (x + 128, y + 100), image)
        draw.text((x + 10, y + 138), f"hotspot {hotspot}", fill="#a6b9c8", font=label_font)
    sheet.save(ROOT / "preview.png")


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    assets = {
        "normal-select.cur": (normal_cursor(), (5, 4)),
        "help-select.cur": (icon(help_cursor, pointer=True), (5, 4)),
        "working-background.cur": (icon(background_cursor, pointer=True), (5, 4)),
        "busy.cur": (icon(busy_cursor), (16, 16)),
        "precision-select.cur": (icon(precision_cursor), (16, 16)),
        "text-select.cur": (icon(text_cursor), (16, 16)),
        "handwriting.cur": (icon(handwriting_cursor), (5, 27)),
        "unavailable.cur": (icon(unavailable_cursor), (16, 16)),
        "vertical-resize.cur": (icon(vertical_resize), (16, 16)),
        "horizontal-resize.cur": (icon(horizontal_resize), (16, 16)),
        "diagonal-resize-1.cur": (icon(diagonal_resize_one), (16, 16)),
        "diagonal-resize-2.cur": (icon(diagonal_resize_two), (16, 16)),
        "move.cur": (icon(move_cursor), (16, 16)),
        "alternate-select.cur": (icon(alternate_cursor), (16, 3)),
        "link-select.cur": (icon(link_cursor), (14, 3)),
        "location-select.cur": (icon(location_cursor), (16, 29)),
        "person-select.cur": (icon(person_cursor), (16, 16)),
        "pin.cur": (icon(pin_cursor), (16, 29)),
    }
    for filename, (image, hotspot) in assets.items():
        write_cur(image, ROOT / filename, hotspot)
    for name, drawer, pointer, hotspot in [
        ("busy", busy_cursor, False, (16, 16)),
        ("working-background", background_cursor, True, (5, 4)),
    ]:
        frames = [icon(lambda draw, phase=step * 30: drawer(draw, phase), pointer=pointer)
                  for step in range(12)]
        write_ani(frames, ROOT / f"{name}.ani", hotspot)
    write_preview(assets)
    # Keep the legacy root-level copy in sync with the theme's normal pointer.
    write_cur(assets["normal-select.cur"][0], ROOT.parent / "VoidCompassCursor.cur", (5, 4))
    print(f"Generated {len(assets)} static and 2 animated cursor files in {ROOT}")


if __name__ == "__main__":
    main()
