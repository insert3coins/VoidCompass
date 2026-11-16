"""A saved Rhino site written up (5.8.3): where it is, its deposits, its runs
and what each commodity earned, as plain text that reads well pasted into
Discord (bold names, one line a fact) and fits one message."""
from __future__ import annotations

import time

DISCORD_LIMIT = 2000
MAX_DEPOSITS = 10
MAX_RUNS = 8


def _date(seconds):
    try:
        return time.strftime("%d %b %Y", time.localtime(float(seconds))).lstrip("0")
    except (TypeError, ValueError, OverflowError, OSError):
        return ""


def credits_text(value):
    value = float(value or 0)
    if value >= 1e9:
        return f"{value / 1e9:.2f}B"
    if value >= 1e6:
        return f"{value / 1e6:.1f}M"
    if value >= 1e3:
        return f"{round(value / 1e3):,}K"
    return f"{round(value):,}"


def _distance(metres):
    metres = float(metres or 0)
    return f"{metres / 1000:.1f} km" if metres >= 1000 else f"{round(metres)} m"


def short_body(system, body):
    body, system = str(body or ""), str(system or "")
    return body[len(system) + 1:] if system and body.casefold().startswith(f"{system} ".casefold()) else body


def earnings(site, prices):
    """What a site's runs took, by commodity, with what it's worth at
    ``prices``: ([{"commodity", "t", "price", "credits"}] most earned first,
    the total in credits). With no runs kept, what your rigs gave there."""
    totals = {}
    for run in site.get("runs") or ():
        for name, tonnes in (run.get("taken") or {}).items():
            totals[name] = totals.get(name, 0) + int(tonnes or 0)
    if not totals:
        totals = {name: int(tonnes or 0) for name, tonnes in (site.get("tonnes") or {}).items()}
    folded = {str(name).casefold(): value for name, value in (prices or {}).items() if value}
    rows = []
    for name, tonnes in totals.items():
        if tonnes <= 0:
            continue
        price = folded.get(str(name).casefold())
        rows.append({"commodity": name, "t": tonnes, "price": round(price) if price else None,
                     "credits": round(price * tonnes) if price else None})
    rows.sort(key=lambda row: (-(row["credits"] or 0), -row["t"], row["commodity"]))
    return rows, sum(row["credits"] or 0 for row in rows)


def site_report(site, deposits=(), prices=None, summary=None, commodity_of=None):
    """The site as text. ``site`` is a saved site (with its system and body),
    ``deposits`` its marked deposits (planet-material rows), ``summary`` its
    runs_summary(), ``commodity_of`` names a deposit's commodity."""
    name = str(site.get("name") or "Mining location")
    where = [str(site.get("system") or ""), short_body(site.get("system"), site.get("body"))]
    if site.get("signal") is not None:
        where.append(f"signal {site['signal']}")
    lines = [f"**{name}**", " · ".join(part for part in where if part)]
    centre = site.get("centre") or ()
    survey = site.get("survey") or {}
    if len(centre) == 2:
        place = f"Centre {float(centre[0]):.4f}, {float(centre[1]):.4f}"
        if survey.get("edge"):
            place += f" · survey {_distance(survey.get('radius_m'))} round it, {int(survey.get('percent') or 0)}% swept"
        lines.append(place)
    if str(site.get("note") or "").strip():
        lines.append(f"_{str(site['note']).strip()}_")

    rows = [row for row in deposits or () if isinstance(row, dict)]
    commodity_of = commodity_of or (lambda row: str(row.get("materials") or "").replace(";", ",").split(",")[0].strip())
    if rows:
        live = [row for row in rows if not row.get("depleted")]
        rigs = sum(int(row.get("rigs") or 0) for row in live)
        head = f"{len(live)} live" + (f", {len(rows) - len(live)} worked out" if len(rows) > len(live) else "")
        lines += ["", f"**Deposits** · {head}" + (f" · {rigs} rig spots" if rigs else "")]
        # Alike deposits go on one line: "Iridium · 3 rigs · High ×2".
        alike = {}
        for row in sorted(rows, key=lambda item: (bool(item.get("depleted")), -int(item.get("rigs") or 0))):
            facts = [commodity_of(row) or "Deposit"]
            if row.get("rigs"):
                facts.append(f"{int(row['rigs'])} rigs")
            if row.get("depleted"):
                facts.append("worked out")
            else:
                facts += [str(row[key]) for key in ("amount", "density") if row.get(key)]
            line = " · ".join(facts)
            alike[line] = alike.get(line, 0) + 1
        shown = list(alike.items())
        for line, count in shown[:MAX_DEPOSITS]:
            lines.append(f"• {line}" + (f" ×{count}" if count > 1 else ""))
        if len(shown) > MAX_DEPOSITS:
            lines.append(f"• and {sum(count for _line, count in shown[MAX_DEPOSITS:])} more")

    summary = summary or {}
    runs = summary.get("runs") or []
    run_lines = []
    for run in runs[:MAX_RUNS]:
        parts = [_date(run.get("docked")), f"{round(float(run.get('minutes') or 0))} min", f"{int(run.get('refined_t') or 0)} t"]
        if run.get("tph"):
            parts.append(f"{round(run['tph'])} t/h")
        run_lines.append("• " + " · ".join(part for part in parts if part))
    runs_head = []
    if runs:
        rate = f" · usual {round(summary['usual_tph'])} t/h · best {round(summary['best_tph'])} t/h" if summary.get("best_tph") else ""
        runs_head = ["", f"**Runs** · {summary.get('count', len(runs))} · {int(summary.get('tonnes') or 0):,} t{rate}"]

    earned, total = earnings(site, prices)
    tail = []
    if earned:
        tail += ["", "**Taken** · at your sale price, else the usual one"]
        for row in earned:
            worth = f" · ~{credits_text(row['credits'])} CR" if row["credits"] else " · no price yet"
            tail.append(f"• {row['commodity']} · {row['t']:,} t{worth}")
        if total:
            tail.append(f"Worth ~{credits_text(total)} CR in all")
    dates = [f"Saved {_date(site['saved'])}" if site.get("saved") else "",
             f"last worked {_date(summary['last'])}" if summary.get("last") else ""]
    tail += ["", " · ".join(part for part in dates + ["VoidCompass"] if part)]

    def joined():
        return "\n".join(lines + runs_head + run_lines + tail)
    # One Discord message: the oldest runs go first, then the deposits.
    deposit_lines = [index for index, line in enumerate(lines) if line.startswith("• ")]
    while len(joined()) > DISCORD_LIMIT and (run_lines or deposit_lines):
        if run_lines:
            run_lines.pop()
        else:
            del lines[deposit_lines.pop()]
    return joined()


__all__ = ["DISCORD_LIMIT", "credits_text", "earnings", "short_body", "site_report"]
