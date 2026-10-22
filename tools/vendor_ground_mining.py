"""Vendor the ground mining table into data/rhino_mining_sheet.json.

The Winters Frosty Wiki's Ground Mining Table (generated from EDIntel, the
table EDRhinoSpotter shows in EDMC) says, for each kind of ground, how often
each material turned up at the mining locations read, and its median and best
price a tonne. Used with permission.

    python tools/vendor_ground_mining.py                 # from the wiki
    python tools/vendor_ground_mining.py saved_page.html # from a saved copy
"""

from __future__ import annotations

import html
import json
import re
import sys
import urllib.request
from pathlib import Path

URL = "https://wiknow.pages.dev/ref/ground-mining"
OUT = Path(__file__).resolve().parents[1] / "data" / "rhino_mining_sheet.json"
# The table's columns, as rhino_intelligence.classify_ground names grounds.
GROUNDS = ("metal-rich", "high-metal-content", "rock 80%+ [none]", "rock 80%+ [metallic magma]",
           "rock 80%+ [rocky magma]", "rock 80%+ [silicate vapour geysers]", "rocky-ice", "icy")


def _price(text):
    match = re.fullmatch(r"([\d.]+)\s*([kKmM]?)", text.strip())
    if not match:
        return None
    return round(float(match.group(1)) * {"": 1, "k": 1e3, "m": 1e6}[match.group(2).lower()])


def parse(page):
    body = page[page.index("<tbody>"):page.index("</tbody>")]
    grounds = {ground: [] for ground in GROUNDS}
    for row in re.findall(r"<tr>(.*?)</tr>", body, re.S):
        cells = [html.unescape(re.sub(r"<[^>]+>", "", cell)).strip() for cell in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if len(cells) != 1 + len(GROUNDS) + 2:
            continue
        material, shares, (median, best) = cells[0], cells[1:-2], cells[-2:]
        for ground, share in zip(GROUNDS, shares):
            if share.endswith("%"):
                grounds[ground].append({"material": material, "pct": float(share[:-1]),
                                        "median": _price(median), "best": _price(best)})
    for rows in grounds.values():
        rows.sort(key=lambda row: (-row["pct"], row["material"]))
    stamp = re.search(r"Generated from EDIntel,\s*([\d-]+ [\d:]+)", page)
    return {
        "generated": f"{stamp.group(1)} UTC" if stamp else None,
        "source": "EDIntel ground mining table (Winters Frosty Wiki, as EDRhinoSpotter shows it)",
        "note": ("Percentages are the share of a ground's mining locations that carried the material: a signal says "
                 "it is there to find, not how much. A ground is the body class; a Rocky body splits on its "
                 "volcanism. Prices exclude Ega, fleet carriers, on-foot settlements and demand-999999 rows."),
        "locations": {},
        "grounds": grounds,
    }


def main(argv):
    if len(argv) > 1:
        page = Path(argv[1]).read_text(encoding="utf-8")
    else:
        request = urllib.request.Request(URL, headers={"User-Agent": "VoidCompass vendor script"})
        with urllib.request.urlopen(request, timeout=30) as response:
            page = response.read().decode("utf-8")
    sheet = parse(page)
    OUT.write_text(json.dumps(sheet, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{OUT}: {sum(len(rows) for rows in sheet['grounds'].values())} rows, generated {sheet['generated']}")


if __name__ == "__main__":
    main(sys.argv)
