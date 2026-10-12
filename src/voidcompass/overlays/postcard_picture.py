"""Postcards as pictures (5.5.3.7): the card the overlay shows, drawn into a
PNG with Pillow, so it can be kept and shared. The same Polaroid: the theme's
light ink warmed for the paper, its dark ground for the writing, Segoe Print
for the handwriting and Bahnschrift for the rest, tilted a touch on a
transparent ground with a soft shadow.

Saved (with Settings > Save postcards as pictures) in a Postcards folder
beside the screenshots. Drawn from the screenshot itself, not the overlay,
so it works with the overlay off and at full quality.
"""
from __future__ import annotations

import io
import os
import re

PHOTO_WIDTH = 1280
# Picture and card measures at PHOTO_WIDTH; everything scales with it.
BORDER, CAPTION_PAD, BOTTOM = 44, 26, 34
TILT_DEGREES = -1.2


def _hex(colour, fallback):
    match = re.fullmatch(r"#?([0-9a-fA-F]{6})", str(colour or "").strip())
    value = match.group(1) if match else fallback.lstrip("#")
    return tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))


def _mix(a, b, share):
    """``share`` of a, the rest b."""
    return tuple(round(x * share + y * (1 - share)) for x, y in zip(a, b))


def card_colours(palette=None, style="polaroid"):
    """Paper, ink and the greeting's colour for a style, as the overlay's
    stylesheet sets them: Polaroid and Holo from the theme, Airmail and
    Vintage their own (5.5.3.7)."""
    palette = palette or {}
    text = _hex(palette.get("text"), "#dce8ef")
    yellow = _hex(palette.get("yellow"), "#ffd166")
    ground = _hex(palette.get("bg"), "#070b10")
    accent = _hex(palette.get("accent"), "#00d1ff")
    if style == "airmail":
        return {"paper": _hex("#f6eedb", ""), "ink": _hex("#1f2a44", ""), "soft": _hex("#5b6478", ""),
                "greet": _hex("#c8323c", ""), "stripes": (_hex("#c8323c", ""), _hex("#2a4c9a", ""))}
    if style == "vintage":
        return {"paper": _hex("#e9dab6", ""), "ink": _hex("#3b2a1a", ""), "soft": _hex("#7a6347", ""),
                "greet": _hex("#b4532a", "")}
    if style == "holo":
        panel = _hex(palette.get("panel"), "#0d141c")
        return {"paper": _mix(panel, accent, .92), "ink": text, "soft": _mix(accent, _hex(palette.get("muted"), "#85939d"), .55),
                "greet": accent, "edge": accent}
    paper = _mix(text, yellow, .9)
    return {"paper": paper, "ink": ground, "soft": _mix(ground, paper, .62),
            "greet": _hex(palette.get("orange"), "#ff7a18")}


def _font(kind, size):
    """Segoe Print (handwriting) or Bahnschrift, from Windows' own fonts;
    Pillow's built-in face elsewhere."""
    from PIL import ImageFont
    names = {"hand": ("segoepr.ttf", "Inkfree.ttf"), "hud": ("bahnschrift.ttf", "segoeui.ttf"),
             "serif": ("georgiaz.ttf", "georgiab.ttf", "timesbi.ttf", "bahnschrift.ttf")}[kind]
    folder = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    for name in names:
        try:
            font = ImageFont.truetype(os.path.join(folder, name), size)
        except OSError:
            continue
        if name == "bahnschrift.ttf":
            for style in (b"Bold SemiCondensed", b"SemiBold SemiCondensed", b"Bold"):
                try:
                    font.set_variation_by_name(style)
                    break
                except (OSError, ValueError):
                    continue
        return font
    try:
        return ImageFont.load_default(size)
    except TypeError:
        return ImageFont.load_default()


def open_picture(path):
    """The screenshot as an RGB image, or None if it can't be read yet (the
    game may still be writing it)."""
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        with Image.open(path) as image:
            image.load()
            return image.convert("RGB")
    except (OSError, ValueError):
        return None


def jpeg_thumbnail(picture, width):
    """A small JPEG of the picture for the overlay's card."""
    small = picture.copy()
    small.thumbnail((width, width * 2))
    out = io.BytesIO()
    small.save(out, "JPEG", quality=84, optimize=True)
    return out.getvalue()


def _cover(picture, width, height):
    """The picture cropped to fill width x height from its middle."""
    from PIL import Image
    scale = max(width / picture.width, height / picture.height)
    resized = picture.resize((max(width, round(picture.width * scale)), max(height, round(picture.height * scale))),
                             Image.LANCZOS)
    left, top = (resized.width - width) // 2, (resized.height - height) // 2
    return resized.crop((left, top, left + width, top + height))


def _spaced(draw, xy, text, font, fill, spacing):
    """Letter-spaced capitals, as the overlay sets its small lines."""
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += draw.textlength(ch, font=font) + spacing
    return x


def _spaced_width(draw, text, font, spacing):
    return sum(draw.textlength(ch, font=font) + spacing for ch in text) - (spacing if text else 0)


def _fit(draw, text, font, width):
    """The text, cut with an ellipsis to fit the width."""
    if draw.textlength(text, font=font) <= width:
        return text
    while text and draw.textlength(text + "…", font=font) > width:
        text = text[:-1]
    return text.rstrip() + "…"


def _wrap(draw, text, font, width):
    """Words in lines that fit the width."""
    lines, line = [], ""
    for word in str(text or "").split():
        trial = f"{line} {word}".strip()
        if line and draw.textlength(trial, font=font) > width:
            lines.append(line)
            line = word
        else:
            line = trial
    if line:
        lines.append(line)
    return lines


def _slanted_text(text, font, fill, shadow, k, lean=0.158):
    """The place's name in slanted capitals with a hard shadow, on its own
    transparent layer (the overlay's skewX(-9deg))."""
    from PIL import Image, ImageDraw
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    left, top, right, bottom = probe.textbbox((0, 0), text, font=font)
    lift = round(4 * k)
    width, height = right + round(40 * k), bottom + lift + round(6 * k)
    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.text((0, lift), text, font=font, fill=shadow)
    draw.text((0, 0), text, font=font, fill=fill)
    # tan(9 degrees): the top leans right, the baseline stays put.
    if not lean:
        return layer
    return layer.transform(layer.size, Image.AFFINE, (1, lean, -lean * height, 0, 1, 0), resample=Image.BICUBIC)


def _greeting(card, width, k, colours, on_photo, style="polaroid"):
    """'Greetings from…': the place in big slanted HUD-orange capitals with
    the system and region under it (5.5.3.7). An RGBA layer ``width`` wide."""
    from PIL import Image, ImageDraw
    small = _font("hud", round(34 * k))
    tiny = _font("hud", round(31 * k))
    light = (255, 255, 255, 235) if on_photo else colours["soft"] + (255,)
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    # Vintage writes it in an italic serif, as it is; the rest in slanted
    # HUD capitals.
    vintage = style == "vintage"
    kind = "serif" if vintage else "hud"
    place = str(card.get("title") or "") if vintage else str(card.get("title") or "").upper()
    size = round((104 if vintage else 120) * k)
    font = _font(kind, size)
    while size > round(48 * k) and probe.textlength(place, font=font) > width - round(70 * k):
        size -= max(1, round(4 * k))
        font = _font(kind, size)
    name = _slanted_text(place, font, colours["greet"] + (255,), (0, 0, 0, 215) if on_photo else colours["ink"] + (90,), k,
                         lean=0 if vintage else 0.158)
    under = " · ".join(part for part in (card.get("place"), card.get("region")) if part).upper()
    # The lettering over the name (5.5.3.8): the card's own words, or none.
    words = str(card.get("greeting", "Greetings from") or "").strip().upper()
    top = round(44 * k) if words else 0
    height = top + round(2 * k) + name.height + (round(42 * k) if under else 0)
    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    if words:
        _spaced(draw, (0, 0), _fit(draw, words, small, width), small, light, round(10 * k))
    layer.alpha_composite(name, (0, top))
    if under:
        text = _fit(draw, under, tiny, width)
        _spaced(draw, (round(4 * k), round(46 * k) + name.height - round(4 * k)), text, tiny, light, round(6 * k))
    return layer


def _stripes(size, k, colours, band):
    """Airmail's red-and-blue striped border, ``band`` px deep (RGBA)."""
    from PIL import Image, ImageDraw
    width, height = size
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    red, blue = colours["stripes"]
    unit = round(34 * k)
    pattern = ((red, round(.32 * unit)), (colours["paper"], round(.18 * unit)), (blue, round(.32 * unit)), (colours["paper"], round(.18 * unit)))
    period = sum(part for _colour, part in pattern)
    for start in range(-height, width + period, period):
        offset = start
        for colour, part in pattern:
            draw.polygon([(offset, height), (offset + part, height), (offset + part + height, 0), (offset + height, 0)],
                         fill=colour + (255,))
            offset += part
    mask = Image.new("L", size, 255)
    ImageDraw.Draw(mask).rectangle([band, band, width - band - 1, height - band - 1], fill=0)
    layer.putalpha(mask)
    return layer


def _sepia(picture):
    """The picture as an old photograph."""
    from PIL import Image, ImageOps
    toned = ImageOps.colorize(ImageOps.grayscale(picture), "#2b1d0e", "#f3e2c0")
    return Image.blend(picture.convert("RGB"), toned, .6)


def render_postcard(card, picture=None, palette=None, width=PHOTO_WIDTH, style="polaroid"):
    """The postcard as an RGBA image, as the overlay draws it: the picture
    with "Greetings from…" over it (or on the paper when there's no
    picture), the Watcher's note, the journal's facts, where and when; tilted
    on a transparent ground with a shadow."""
    from PIL import Image, ImageDraw, ImageFilter
    style = style if style in ("polaroid", "airmail", "holo", "vintage") else "polaroid"
    colours = card_colours(palette, style)
    if style == "vintage" and picture is not None:
        picture = _sepia(picture)
    k = width / PHOTO_WIDTH
    border, pad, bottom = round(BORDER * k), round(CAPTION_PAD * k), round(BOTTOM * k)
    hand, signed_font = _font("hand", round(50 * k)), _font("hand", round(46 * k))
    small = _font("hud", round(32 * k))
    chip_font = _font("hud", round(28 * k))
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    # Airmail's stripes take a band of the border: its words keep clear.
    inset = round(22 * k) if style == "airmail" else 0
    room = width - round(12 * k) - inset * 2
    photo_height = round(width * 9 / 16) if picture is not None else 0
    greeting = _greeting(card, room, k, colours, on_photo=picture is not None, style=style)

    # Measure the paper's lines first, then draw them.
    note = str(card.get("note") or "")
    note_lines = _wrap(probe, note or card.get("doing") or "", hand, room)
    line_h = round(66 * k)
    chips = [str(fact).upper() for fact in card.get("facts") or ()]
    chip_h, chip_gap, chip_pad = round(46 * k), round(12 * k), round(16 * k)
    chip_rows, row, used = [], [], 0
    for chip in chips:
        chip_w = round(probe.textlength(chip, font=chip_font)) + chip_pad * 2 + round(len(chip) * 2.6 * k)
        if row and used + chip_w > room:
            chip_rows.append(row)
            row, used = [], 0
        row.append((chip, chip_w))
        used += chip_w + chip_gap
    if row:
        chip_rows.append(row)
    where = " · ".join(part for part in ((card.get("doing") if note else ""), card.get("coordinates")) if part).upper()
    caption_height = (pad + (greeting.height + round(20 * k) if picture is None else 0)
                      + len(note_lines) * line_h + (round(80 * k) if note else 0)
                      + len(chip_rows) * (chip_h + chip_gap) + round(10 * k)
                      + (round(48 * k) if where else 0) + round(24 * k) + round(48 * k))
    card_width, card_height = width + border * 2, border + photo_height + caption_height + bottom
    paper = Image.new("RGBA", (card_width, card_height), colours["paper"] + (255,))
    draw = ImageDraw.Draw(paper)
    x = border + round(6 * k) + inset

    if picture is not None:
        photo = _cover(picture, width, photo_height).convert("RGBA")
        if style == "holo":
            # A display's scanlines over the picture.
            lines = Image.new("RGBA", photo.size, (0, 0, 0, 0))
            line_draw = ImageDraw.Draw(lines)
            for row_y in range(0, photo_height, max(3, round(4 * k))):
                line_draw.line([(0, row_y), (width, row_y)], fill=(0, 0, 0, 56), width=max(1, round(1.2 * k)))
            photo.alpha_composite(lines)
        # A shade under the lettering, as the overlay's gradient.
        shade = Image.new("L", (1, 256))
        for index in range(256):
            shade.putpixel((0, index), round(max(0, (index - 70) / 186) * 185))
        tall = min(photo_height, greeting.height + round(130 * k))
        mask = shade.resize((width, tall))
        dark = Image.new("RGBA", (width, tall), (0, 0, 0, 255))
        photo.paste(dark, (0, photo_height - tall), mask)
        photo.alpha_composite(greeting, (round(40 * k), photo_height - greeting.height - round(30 * k)))
        paper.alpha_composite(photo, (border, border))
        y = border + photo_height + pad
    else:
        y = border + pad
        paper.alpha_composite(greeting, (x, y))
        y += greeting.height + round(20 * k)

    for line in note_lines:
        draw.text((x, y), line, font=hand, fill=colours["ink"])
        y += line_h
    if note:
        signature = "— the Watcher"
        draw.text((x + room - draw.textlength(signature, font=signed_font), y), signature,
                  font=signed_font, fill=colours["soft"])
        y += round(80 * k)
    spacing = round(3 * k)
    for chips_row in chip_rows:
        left = x
        for chip, chip_w in chips_row:
            draw.rounded_rectangle([left, y, left + chip_w, y + chip_h], radius=round(6 * k),
                                   outline=_mix(colours["ink"], colours["paper"], .3), width=max(1, round(3 * k)))
            _spaced(draw, (left + chip_pad, y + round(7 * k)), chip, chip_font, colours["soft"], spacing)
            left += chip_w + chip_gap
        y += chip_h + chip_gap
    y += round(10 * k)
    if where:
        _spaced(draw, (x, y), _fit(draw, where, small, room), small, colours["soft"], round(4 * k))
        y += round(48 * k)
    # The dashed rule, then the date and the time.
    dash = round(10 * k)
    for left in range(x, x + room, dash * 2):
        draw.line([(left, y), (min(left + dash, x + room), y)], fill=_mix(colours["ink"], colours["paper"], .25),
                  width=max(1, round(2 * k)))
    y += round(18 * k)
    _spaced(draw, (x, y), str(card.get("date") or ""), small, colours["soft"], round(5 * k))
    when = str(card.get("time") or "")
    if when:
        _spaced(draw, (x + room - _spaced_width(draw, when, small, round(5 * k)), y), when, small, colours["soft"], round(5 * k))

    # The style's frame: Airmail's stripes, Holo's lit edge and brackets.
    if style == "airmail":
        paper.alpha_composite(_stripes(paper.size, k, colours, round(26 * k)))
    elif style == "holo":
        edge = colours["edge"] + (255,)
        draw.rectangle([0, 0, card_width - 1, card_height - 1], outline=_mix(colours["edge"], colours["paper"], .6),
                       width=max(1, round(3 * k)))
        arm, thick = round(54 * k), max(2, round(7 * k))
        draw.rectangle([0, 0, arm, thick], fill=edge)
        draw.rectangle([0, 0, thick, arm], fill=edge)
        draw.rectangle([card_width - arm, card_height - thick, card_width, card_height], fill=edge)
        draw.rectangle([card_width - thick, card_height - arm, card_width, card_height], fill=edge)

    # On a transparent ground, with a soft shadow, tilted a touch.
    margin = round(56 * k)
    ground = Image.new("RGBA", (card_width + margin * 2, card_height + margin * 2), (0, 0, 0, 0))
    shadow = Image.new("RGBA", ground.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rectangle(
        [margin, margin + round(14 * k), margin + card_width, margin + card_height + round(14 * k)], fill=(0, 0, 0, 140))
    ground = Image.alpha_composite(ground, shadow.filter(ImageFilter.GaussianBlur(round(18 * k))))
    ground.alpha_composite(paper, (margin, margin))
    return ground.rotate(TILT_DEGREES, resample=Image.BICUBIC, expand=True)


def postcard_filename(card, stamp):
    """``Postcard - Hatchooe AB 3 - 2026-10-11 20-14-00.png``"""
    title = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", str(card.get("title") or "Postcard")).strip(" .") or "Postcard"
    return f"Postcard - {title[:80]} - {stamp}.png"


def save_postcard_picture(card, picture, folder, palette=None, stamp=None, style="polaroid"):
    """Draw the postcard and save it in ``folder`` (made if need be); its
    path, or None."""
    import time
    stamp = stamp or time.strftime("%Y-%m-%d %H-%M-%S")
    try:
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, postcard_filename(card, stamp))
        base, counter = os.path.splitext(path)[0], 1
        while os.path.exists(path):
            path = f"{base} ({counter}).png"
            counter += 1
        image = render_postcard(card, picture, palette, style=style)
        partial = path + ".part"
        image.save(partial, "PNG", optimize=True)
        os.replace(partial, path)
        return path
    except OSError:
        return None
