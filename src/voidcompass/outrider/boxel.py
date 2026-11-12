"""Boxels: the cubes a procedural system name places a system in (the author's boxel exploration, 2026-10-11). Pure.

A procedural name is `<Sector> <L0><L1>-<L2> <mass code>[<n1>-]<n2>`. Sectors are 1280 ly cubes on a fixed grid from
ORIGIN; each mass code a..h cuts a sector into cubes ("boxels", Frontier's subsectors) of 10, 20, 40 ... 1280 ly. The
letters and n1 are the boxel's place in its sector (p = x + 128y + 16384z, in base 26); n2 numbers its systems from 0,
without gaps. The system address (id64) packs the same: n2, sector x, boxel x, sector y, boxel y, sector z, boxel z,
the mass code. Both checked against the author's journals: 2,763 of 2,763 standard-sector systems.

Hand-authored sectors and regions ("Col 285 Sector", "ICZ", "Scorpius Dark Region") lay their boxels out from their
own origins: their names still parse (the list of a boxel works by name), the geometry does not (`standard` False).
Sector names are not generated here: a sector's name is known from a system seen in it.
"""
import math
import re

NAME = re.compile(r"^(?P<sector>.+) (?P<l0>[A-Z])(?P<l1>[A-Z])-(?P<l2>[A-Z]) (?P<mc>[a-h])(?:(?P<n1>\d+)-)?(?P<n2>\d+)$")
ORIGIN = (-49985.0, -40985.0, -24105.0)   # the sector grid's corner (ly)
SECTOR = 1280                             # a sector's side (ly)
CODES = "abcdefgh"
TRY_ABOVE = 5        # numbers offered above the highest known one, until a name is not found

# What each mass code tends to hold: community observations of how boxels' stars come out, not rules of the game.
KINDS = {
    "a": "brown dwarfs and dim red dwarfs: few bodies, little value",
    "b": "mostly M red dwarfs, some K: icy and rocky bodies, biology possible",
    "c": "K and M stars, some G: more planets, fair odds of biology",
    "d": "F, G and K stars, some A: the best odds of Earth-likes, water worlds, terraformables and varied biology",
    "e": "A and B stars: hot, younger systems, fewer Earth-likes",
    "f": "B and O stars and white dwarfs: rare and spread out",
    "g": "giants and supergiants, neutron stars, Wolf-Rayets: few per sector",
    "h": "the most massive: supergiants and black holes, one boxel the size of the sector",
}


def size(mc):
    """A boxel's side in light years for mass code `mc` ("a" 10 ... "h" 1280)."""
    return 10 << CODES.index(mc)


def parse(name):
    """{sector, letters ("AB-C"), mc, n1, n2, prefix (the name less n2: name_of adds a number), label} for a procedural
    name, else None (a hand-named system such as "Sol" has no boxel)."""
    m = NAME.match(" ".join(str(name or "").split()))
    if not m:
        return None
    n2 = m["n2"]
    prefix = m.string[:len(m.string) - len(n2)]
    return {"sector": m["sector"], "letters": f"{m['l0']}{m['l1']}-{m['l2']}", "mc": m["mc"],
            "n1": int(m["n1"]) if m["n1"] is not None else 0, "n2": int(n2), "prefix": prefix,
            "label": prefix[:-1] if prefix.endswith("-") else prefix}


def name_of(prefix, n):
    """The name of system number `n` of the boxel `prefix` ("Smojooe XF-G b24-" + 3)."""
    return f"{prefix}{int(n)}"


def number_of(prefix, name):
    """The number of `name` in boxel `prefix`, or None when it is not one of its systems."""
    rest = str(name or "")[len(prefix):] if str(name or "").startswith(prefix) else ""
    return int(rest) if rest.isdigit() and (rest == "0" or not rest.startswith("0")) else None


def locate(pos, mc):
    """(sector (sx, sy, sz), boxel (bx, by, bz)) of a position for mass code `mc`."""
    s = size(mc)
    rel = [pos[k] - o for k, o in zip(("x", "y", "z"), ORIGIN)]
    sector = tuple(int(math.floor(v / SECTOR)) for v in rel)
    boxel = tuple(int(math.floor((v - SECTOR * sc) / s)) for v, sc in zip(rel, sector))
    return sector, boxel


def letters(boxel):
    """("AB-C", n1): the letters and the overflow number a boxel's place in its sector gives."""
    bx, by, bz = boxel
    p = bx + by * 128 + bz * 16384
    return f"{chr(65 + p % 26)}{chr(65 + p // 26 % 26)}-{chr(65 + p // 676 % 26)}", p // 17576


def boxel_index(lett, n1):
    """The boxel (bx, by, bz) from its letters and overflow number: letters() backwards."""
    l0, l1, l2 = (ord(c) - 65 for c in (lett[0], lett[1], lett[3]))
    p = l0 + l1 * 26 + l2 * 676 + n1 * 17576
    return p % 128, p // 128 % 128, p // 16384


def id64(sector, boxel, mc, n2):
    """The system address of system n2 of a boxel (n2, then sector x / boxel x, y, z, then the mass code)."""
    bits = 7 - CODES.index(mc)
    v = int(n2)
    for part, width in ((sector[0], 7), (boxel[0], bits), (sector[1], 6), (boxel[1], bits), (sector[2], 7), (boxel[2], bits)):
        v = (v << width) | int(part)
    return (v << 3) | CODES.index(mc)


def of_system(name, pos=None):
    """The boxel of a system: parse()'s fields, plus (when `pos` is given and the sector is a standard one, i.e. the
    letters the position gives are the name's) sector_index, boxel, center and standard True; else standard False."""
    p = parse(name)
    if not p:
        return None
    p["standard"] = False
    if pos and all(isinstance(pos.get(k), (int, float)) for k in ("x", "y", "z")):
        sector, boxel = locate(pos, p["mc"])
        if letters(boxel) == (p["letters"], p["n1"]):
            p.update(standard=True, sector_index=list(sector), boxel=list(boxel), center=center(sector, boxel, p["mc"]))
    return p


def center(sector, boxel, mc):
    """A boxel's centre {x, y, z}."""
    s = size(mc)
    return {k: round(o + SECTOR * sc + s * (b + 0.5), 3) for k, o, sc, b in zip(("x", "y", "z"), ORIGIN, sector, boxel)}


def boxel_of(sector_name, sector, boxel, mc):
    """The full boxel record for a place in a named sector (what of_system gives for a standard name)."""
    lett, n1 = letters(boxel)
    prefix = f"{sector_name} {lett} {mc}" + (f"{n1}-" if n1 else "")
    return {"sector": sector_name, "letters": lett, "mc": mc, "n1": n1, "prefix": prefix,
            "label": prefix[:-1] if prefix.endswith("-") else prefix, "standard": True,
            "sector_index": list(sector), "boxel": list(boxel), "center": center(sector, boxel, mc)}


def dist(a, b):
    return math.dist((a["x"], a["y"], a["z"]), (b["x"], b["y"], b["z"]))


def nearby(pos, sector_names, codes="bcdef", per_code=3, reach=2):
    """The boxels nearest `pos` for each mass code in `codes`: [{...boxel_of(), distance (to its centre)}], per_code
    of each, nearest first. Only in sectors whose name is known (`sector_names`: {(sx, sy, sz): name}); `reach`
    boxels each way of the one you are in are looked at (more for the small codes would only add the far ones)."""
    out = []
    for mc in codes:
        sector, boxel = locate(pos, mc)
        n = SECTOR // size(mc)
        cands = []
        for dx in range(-reach, reach + 1):
            for dy in range(-reach, reach + 1):
                for dz in range(-reach, reach + 1):
                    g = [sector[i] * n + boxel[i] + d for i, d in enumerate((dx, dy, dz))]   # a boxel on the galaxy's grid
                    sec, box = tuple(v // n for v in g), tuple(v % n for v in g)
                    sname = sector_names.get(sec)
                    if not sname:
                        continue
                    b = boxel_of(sname, sec, box, mc)
                    b["distance"] = round(dist(pos, b["center"]), 1)
                    cands.append(b)
        out += sorted(cands, key=lambda b: b["distance"])[:per_code]
    return out
