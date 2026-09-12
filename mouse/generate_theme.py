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
PURPLE = (21, 189, 232, 255)
VIOLET = (20, 118, 201, 255)
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


def arrow(draw: ImageDraw.ImageDraw) -> None:
    shape = pts([(3, 3), (29, 18), (19, 19), (24, 27), (19, 29), (14, 21), (8, 27)])
    draw.polygon(shape, fill=DARK)
    draw.line(shape + [shape[0]], fill=WHITE, width=2 * SCALE, joint="curve")
    inner = pts([(7, 8), (24, 18), (17, 18), (20, 23)])
    draw.line(inner, fill=PURPLE, width=SCALE, joint="curve")


def finish(image: Image.Image) -> Image.Image:
    alpha = image.getchannel("A")
    glow = Image.new("RGBA", image.size, PURPLE)
    glow.putalpha(alpha.filter(ImageFilter.GaussianBlur(2.2 * SCALE)).point(lambda value: int(value * 0.48)))
    return Image.alpha_composite(glow, image).resize((SIZE, SIZE), Image.Resampling.LANCZOS)


def icon(drawer) -> Image.Image:
    image, draw = icon_canvas()
    drawer(draw)
    return finish(image)


def normal_cursor() -> Image.Image:
    image = Image.open(APP_CURSOR).convert("RGBA")
    output = []
    for red, green, blue, alpha in image.getdata():
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
    arrow(draw)
    draw.ellipse(box((16.5, 5.5, 27.5, 16.5)), fill=DARK, outline=GOLD, width=SCALE)
    draw.text(pt(18.9, 4.8), "?", fill=GOLD, font=font(8), stroke_width=0)


def background_cursor(draw: ImageDraw.ImageDraw) -> None:
    arrow(draw)
    draw.arc(box((18, 18, 30, 30)), 35, 315, fill=GOLD, width=SCALE)
    draw.polygon(pts([(26.5, 18.5), (30, 19), (28.5, 22)]), fill=GOLD)


def busy_cursor(draw: ImageDraw.ImageDraw) -> None:
    draw.ellipse(box((5, 5, 27, 27)), outline=VIOLET, width=2 * SCALE)
    for index in range(8):
        start = index * 45 + 5
        colour = GOLD if index in {0, 1} else PURPLE
        draw.arc(box((7, 7, 25, 25)), start, start + 24, fill=colour, width=2 * SCALE)
    draw.ellipse(box((13, 13, 19, 19)), fill=DARK, outline=GOLD, width=SCALE)


def precision_cursor(draw: ImageDraw.ImageDraw) -> None:
    draw.ellipse(box((7, 7, 25, 25)), outline=WHITE, width=SCALE)
    draw.ellipse(box((11, 11, 21, 21)), outline=PURPLE, width=SCALE)
    draw.line([pt(2, 16), pt(30, 16)], fill=PURPLE, width=SCALE)
    draw.line([pt(16, 2), pt(16, 30)], fill=PURPLE, width=SCALE)
    draw.ellipse(box((14.5, 14.5, 17.5, 17.5)), fill=GOLD)


def text_cursor(draw: ImageDraw.ImageDraw) -> None:
    draw.rectangle(box((14, 4, 18, 28)), fill=DARK)
    draw.rectangle(box((15, 5, 17, 27)), fill=PURPLE)
    draw.line([pt(8, 5), pt(24, 5)], fill=WHITE, width=SCALE)
    draw.line([pt(8, 27), pt(24, 27)], fill=WHITE, width=SCALE)


def handwriting_cursor(draw: ImageDraw.ImageDraw) -> None:
    shape = pts([(5, 27), (8, 15), (21, 4), (27, 10), (16, 23)])
    draw.polygon(shape, fill=DARK)
    draw.line(shape + [shape[0]], fill=WHITE, width=2 * SCALE, joint="curve")
    draw.line(pts([(8, 22), (22, 8)]), fill=PURPLE, width=2 * SCALE)
    draw.polygon(pts([(5, 27), (9, 24), (8, 28)]), fill=GOLD)


def unavailable_cursor(draw: ImageDraw.ImageDraw) -> None:
    arrow(draw)
    draw.ellipse(box((14, 13, 29, 28)), fill=DARK, outline=RED, width=2 * SCALE)
    draw.line([pt(17, 16), pt(26, 25)], fill=RED, width=2 * SCALE)


def vertical_resize(draw: ImageDraw.ImageDraw) -> None:
    draw.line([pt(16, 3), pt(16, 29)], fill=WHITE, width=2 * SCALE)
    draw.polygon(pts([(16, 2), (10, 9), (22, 9)]), fill=PURPLE)
    draw.polygon(pts([(16, 30), (10, 23), (22, 23)]), fill=PURPLE)
    draw.ellipse(box((14, 14, 18, 18)), fill=GOLD)


def horizontal_resize(draw: ImageDraw.ImageDraw) -> None:
    draw.line([pt(3, 16), pt(29, 16)], fill=WHITE, width=2 * SCALE)
    draw.polygon(pts([(2, 16), (9, 10), (9, 22)]), fill=PURPLE)
    draw.polygon(pts([(30, 16), (23, 10), (23, 22)]), fill=PURPLE)
    draw.ellipse(box((14, 14, 18, 18)), fill=GOLD)


def diagonal_resize_one(draw: ImageDraw.ImageDraw) -> None:
    draw.line([pt(4, 4), pt(28, 28)], fill=WHITE, width=2 * SCALE)
    draw.polygon(pts([(3, 3), (12, 5), (5, 12)]), fill=PURPLE)
    draw.polygon(pts([(29, 29), (20, 27), (27, 20)]), fill=PURPLE)
    draw.ellipse(box((14, 14, 18, 18)), fill=GOLD)


def diagonal_resize_two(draw: ImageDraw.ImageDraw) -> None:
    draw.line([pt(28, 4), pt(4, 28)], fill=WHITE, width=2 * SCALE)
    draw.polygon(pts([(29, 3), (20, 5), (27, 12)]), fill=PURPLE)
    draw.polygon(pts([(3, 29), (12, 27), (5, 20)]), fill=PURPLE)
    draw.ellipse(box((14, 14, 18, 18)), fill=GOLD)


def move_cursor(draw: ImageDraw.ImageDraw) -> None:
    draw.line([pt(16, 3), pt(16, 29)], fill=WHITE, width=2 * SCALE)
    draw.line([pt(3, 16), pt(29, 16)], fill=WHITE, width=2 * SCALE)
    draw.polygon(pts([(16, 2), (11, 8), (21, 8)]), fill=PURPLE)
    draw.polygon(pts([(16, 30), (11, 24), (21, 24)]), fill=PURPLE)
    draw.polygon(pts([(2, 16), (8, 11), (8, 21)]), fill=PURPLE)
    draw.polygon(pts([(30, 16), (24, 11), (24, 21)]), fill=PURPLE)
    draw.ellipse(box((13, 13, 19, 19)), fill=DARK, outline=GOLD, width=SCALE)


def alternate_cursor(draw: ImageDraw.ImageDraw) -> None:
    draw.polygon(pts([(16, 3), (27, 17), (20, 17), (20, 28), (12, 28), (12, 17), (5, 17)]), fill=DARK)
    draw.line(pts([(16, 3), (27, 17), (20, 17), (20, 28), (12, 28), (12, 17), (5, 17), (16, 3)]), fill=WHITE, width=2 * SCALE, joint="curve")
    draw.line(pts([(16, 7), (16, 24)]), fill=PURPLE, width=SCALE)


def link_cursor(draw: ImageDraw.ImageDraw) -> None:
    palm = pts([(9, 15), (9, 8), (12, 7), (14, 13), (14, 5), (17, 5), (18, 13), (18, 7), (21, 7), (21, 14), (23, 11), (26, 13), (23, 23), (18, 27), (11, 25)])
    draw.polygon(palm, fill=DARK)
    draw.line(palm + [palm[0]], fill=WHITE, width=2 * SCALE, joint="curve")
    draw.line(pts([(12, 9), (12, 19), (16, 23), (21, 19)]), fill=PURPLE, width=SCALE, joint="curve")
    draw.ellipse(box((16, 17, 20, 21)), fill=GOLD)


def location_cursor(draw: ImageDraw.ImageDraw) -> None:
    draw.ellipse(box((7, 3, 25, 21)), fill=DARK, outline=WHITE, width=2 * SCALE)
    draw.polygon(pts([(8, 15), (16, 30), (24, 15)]), fill=DARK)
    draw.line(pts([(8, 15), (16, 30), (24, 15)]), fill=WHITE, width=2 * SCALE, joint="curve")
    draw.ellipse(box((12, 8, 20, 16)), fill=PURPLE, outline=GOLD, width=SCALE)


def person_cursor(draw: ImageDraw.ImageDraw) -> None:
    draw.ellipse(box((11, 3, 21, 13)), fill=DARK, outline=WHITE, width=2 * SCALE)
    draw.polygon(pts([(5, 29), (7, 20), (12, 16), (20, 16), (25, 20), (27, 29)]), fill=DARK)
    draw.line(pts([(5, 29), (7, 20), (12, 16), (20, 16), (25, 20), (27, 29)]), fill=PURPLE, width=2 * SCALE, joint="curve")
    draw.ellipse(box((14, 6, 18, 10)), fill=GOLD)


def pin_cursor(draw: ImageDraw.ImageDraw) -> None:
    draw.ellipse(box((8, 4, 24, 20)), fill=DARK, outline=WHITE, width=2 * SCALE)
    draw.polygon(pts([(10, 17), (22, 17), (16, 30)]), fill=DARK)
    draw.line(pts([(10, 17), (22, 17), (16, 30), (10, 17)]), fill=PURPLE, width=2 * SCALE, joint="curve")
    draw.line(pts([(12, 10), (20, 10)]), fill=GOLD, width=SCALE)


def write_cur(image: Image.Image, path: Path, hotspot: tuple[int, int]) -> None:
    image = image.convert("RGBA").resize((SIZE, SIZE), Image.Resampling.LANCZOS)
    pixels = list(image.getdata())
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
    path.write_bytes(struct.pack("<HHH", 0, 2, 1) + entry + payload)


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    assets = {
        "normal-select.cur": (normal_cursor(), (5, 4)),
        "help-select.cur": (icon(help_cursor), (5, 4)),
        "working-background.cur": (icon(background_cursor), (5, 4)),
        "busy.cur": (icon(busy_cursor), (16, 16)),
        "precision-select.cur": (icon(precision_cursor), (16, 16)),
        "text-select.cur": (icon(text_cursor), (16, 16)),
        "handwriting.cur": (icon(handwriting_cursor), (5, 27)),
        "unavailable.cur": (icon(unavailable_cursor), (5, 4)),
        "vertical-resize.cur": (icon(vertical_resize), (16, 16)),
        "horizontal-resize.cur": (icon(horizontal_resize), (16, 16)),
        "diagonal-resize-1.cur": (icon(diagonal_resize_one), (16, 16)),
        "diagonal-resize-2.cur": (icon(diagonal_resize_two), (16, 16)),
        "move.cur": (icon(move_cursor), (16, 16)),
        "alternate-select.cur": (icon(alternate_cursor), (16, 16)),
        "link-select.cur": (icon(link_cursor), (8, 7)),
        "location-select.cur": (icon(location_cursor), (16, 29)),
        "person-select.cur": (icon(person_cursor), (16, 16)),
        "pin.cur": (icon(pin_cursor), (16, 29)),
    }
    for filename, (image, hotspot) in assets.items():
        write_cur(image, ROOT / filename, hotspot)
    # Keep the legacy root-level copy in sync with the theme's normal pointer.
    write_cur(assets["normal-select.cur"][0], ROOT.parent / "VoidCompassCursor.cur", (5, 4))
    print(f"Generated {len(assets)} cursor files in {ROOT}")


if __name__ == "__main__":
    main()
