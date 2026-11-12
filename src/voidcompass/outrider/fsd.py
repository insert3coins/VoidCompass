"""The frame shift drive's maths: jump range at a mass, fuel per jump, the fuel model fitted to your own jumps, a
fleet ship's figures from its Loadout (the Neutron Highway's plotter inputs), and the conservative range.
Pure functions and constants: no state, no I/O. ed_outrider.py and the Highway use them."""
import re

# The fuel model (fuel_model): a jump of d ly burns MaxFuelPerJump × (d / range at this mass)^p, where p is the game's
# power constant for the drive's size (standard and SCO drives alike, every class), and a Guardian booster adds its
# light years. The Caspian Explorer's Mk II SCO drive has a p of its own. Checked 2026-09-30 against EDCD
# coriolis-data (modules/standard/frame_shift_drive.json "fuelpower", modules/internal/guardian_fsd_booster.json
# "jumpboost") and EDDiscovery's EliteDangerousCore (FrontierData/Items/ModuleList.cs "PowerConstant", which rounds
# the Mk II's 2.5025 to 2.503). Replayed on the author's journals, 2.5025 fits the Mk II's jumps to within 0.2%
# (and its 6.8 t MaxFuelPerJump, as both tables say); a size's p fits every other drive there.
FSD_POWER = {2: 2.00, 3: 2.15, 4: 2.30, 5: 2.45, 6: 2.60, 7: 2.75, 8: 2.90}
FSD_RANGE_MODS = ("FSDOptimalMass", "MaxFuelPerJump", "Mass")   # engineering modifiers that move the range
FSD_POWER_ITEM = {"int_hyperdrive_overcharge_size8_class5_overchargebooster_mkii": 2.5025}
FSD_STANDARD = re.compile(r"int_hyperdrive(?:_overcharge)?_size(\d)_class\d(?:_free)?")   # the size's p holds
GUARDIAN_BOOST = {1: 4.0, 2: 6.0, 3: 7.75, 4: 9.25, 5: 10.5}
# The drives' stock figures for Spansh's exact plotter (fleet_figures): (optimal mass t, MaxFuelPerJump t, fuel multiplier)
# per Loadout item, classes 1-5 being E-A. From EDCD coriolis-data modules/standard/frame_shift_drive.json ("optmass",
# "maxfuel", "fuelmul"), checked 2026-10-01. The multiplier is the class's linear constant / 1000 (E 11, D 10, C 8, B 10,
# A 12; SCO drives E 8, D-B 12, A 13). An engineered drive's FSDOptimalMass and MaxFuelPerJump come from its Modifiers.
FSD_STOCK = {
    "int_hyperdrive_size{}_class{}": ((0.011, 0.010, 0.008, 0.010, 0.012), {
        2: ((48, 54, 60, 75, 90), (0.6, 0.6, 0.6, 0.8, 0.9)), 3: ((80, 90, 100, 125, 150), (1.2, 1.2, 1.2, 1.5, 1.8)),
        4: ((280, 315, 350, 437.5, 525), (2.0, 2.0, 2.0, 2.5, 3.0)), 5: ((560, 630, 700, 875, 1050), (3.3, 3.3, 3.3, 4.1, 5.0)),
        6: ((960, 1080, 1200, 1500, 1800), (5.3, 5.3, 5.3, 6.6, 8.0)),
        7: ((1440, 1620, 1800, 2250, 2700), (8.5, 8.5, 8.5, 10.6, 12.8))}),
    "int_hyperdrive_overcharge_size{}_class{}": ((0.008, 0.012, 0.012, 0.012, 0.013), {
        2: ((60, 90, 90, 90, 100), (0.6, 0.9, 0.9, 0.9, 1.0)), 3: ((100, 150, 150, 150, 167), (1.2, 1.8, 1.8, 1.8, 1.9)),
        4: ((350, 525, 525, 525, 585), (2.0, 3.0, 3.0, 3.0, 3.2)), 5: ((700, 1050, 1050, 1050, 1175), (3.3, 5.0, 5.0, 5.0, 5.2)),
        6: ((1200, 1800, 1800, 1800, 2000), (5.3, 8.0, 8.0, 8.0, 8.3)),
        7: ((1800, 2700, 2700, 2700, 3000), (8.5, 12.8, 12.8, 12.8, 13.1)),
        8: ((2800, 4200, 4200, 4200, 4670), (13.6, 20.4, 20.4, 20.4, 20.7))}),
}
FSD_DATA = {name.format(size, c + 1): (opt[c], mf[c], mul[c])
            for name, (mul, sizes) in FSD_STOCK.items() for size, (opt, mf) in sizes.items() for c in range(5)}
# the Caspian's Mk II: coriolis-data says 0.011 (Auto_Neutron's table says 4/1000). Either way fleet_figures checks the
# figures against the Loadout's own MaxJumpRange and, when they miss it, takes the optimal mass that range implies
FSD_DATA["int_hyperdrive_overcharge_size8_class5_overchargebooster_mkii"] = (4670, 6.8, 0.011)
FSD_MK2_SUPERCHARGE = 6   # the Mk II's neutron supercharge multiplies the range by 6; every other drive by 4
FSD_RANGE_TOLERANCE = 0.01   # the stated figures must give the Loadout's MaxJumpRange to within 1%, or the range decides
FUEL_FIT_MIN = 3          # own jumps (with the fuel left and the cargo known) before MaxFuelPerJump is fitted
FUEL_FIT_POWER_MIN = 5     # ... and before p is fitted, for a drive neither table knows (a new variant)


def fsd_power(ship):
    """The drive's power constant p, or None for a drive the tables don't know (fuel_model then fits it)."""
    item = (ship.get("fsd") or "").lower()
    if not item:   # a ship saved before the drive's name was kept: its size says
        return FSD_POWER.get(ship.get("fsd_size"))
    if item in FSD_POWER_ITEM:
        return FSD_POWER_ITEM[item]
    std = FSD_STANDARD.fullmatch(item)
    return FSD_POWER.get(int(std.group(1))) if std else None


def fsd_range(model, mass, fuel=None):
    """The longest jump at `mass` t. The Loadout's MaxJumpRange is the range at the unladen mass plus one max jump's
    fuel; range goes as 1/mass, the booster's flat light years apart. max_fuel unknown counts as 0 (a small error).
    With `fuel` (t in the main tank) below MaxFuelPerJump, the jump that fuel pays for (hop_fuel's inverse)."""
    b = model["boost"]
    r = (model["r0"] - b) * (model["unladen"] + (model.get("max_fuel") or 0)) / mass + b
    mf, p = model.get("max_fuel"), model.get("power")
    if fuel is not None and mf and p and fuel < mf:
        r *= (max(fuel, 0) / mf) ** (1 / p)
    return r


def hop_fuel(model, d, mass):
    """Fuel for a d ly jump at `mass` t, or None past the range (or without MaxFuelPerJump and p)."""
    if not model.get("max_fuel") or not model.get("power"):
        return None
    r = fsd_range(model, mass)
    return model["max_fuel"] * (d / r) ** model["power"] if 0 <= d <= r + 1e-6 else None


def _fit_estimates(model, samples, power):
    """One MaxFuelPerJump estimate per [ly, fuel used, fuel left, cargo] sample, at power p. The range depends a
    little on the answer (the Loadout's range includes one max jump's fuel), so each is solved by iteration."""
    out = []
    for d, used, left, cargo in samples:
        mass, mf = model["unladen"] + left + used + cargo, 0.0
        for _ in range(12):
            mf = used * (fsd_range(dict(model, max_fuel=mf), mass) / d) ** power
        out.append(mf)
    return out


def fuel_model(ship, samples):
    """The fuel model for a ship's Loadout ({unladen, r0, boost, power, max_fuel, fitted}), or None without the mass.
    p comes from the drive (fsd_power), else is fitted; MaxFuelPerJump from the drive's engineering when it says,
    else the median of your own jumps' estimates. Either can stay None (range still works, per-hop fuel does not);
    `need` is how many more usable jumps they take (0 once both are known)."""
    ship = ship or {}
    if not ship.get("unladen") or not ship.get("max_range"):
        return None
    model = {"unladen": ship["unladen"], "r0": ship["max_range"], "boost": ship.get("booster_ly") or 0,
             "power": fsd_power(ship), "max_fuel": ship.get("max_fuel"), "fitted": False}
    good = [s[:4] for s in samples or [] if len(s) >= 4 and s[2] is not None and s[3] is not None and s[0] > 0 and s[1] > 0]
    if model["power"] is None and len(good) >= FUEL_FIT_POWER_MIN:
        # a drive the tables lack: the known p whose estimates agree best (the right one gives nearly the same
        # figure for a 3 ly hop and a 60 ly one; a wrong one drifts with the distance)
        def spread(p):
            e = sorted(_fit_estimates(model, good, p))
            return (e[-1] - e[0]) / e[len(e) // 2]
        model["power"] = min(sorted(set(FSD_POWER.values()) | set(FSD_POWER_ITEM.values())), key=spread)
    if not model["max_fuel"] and model["power"] and len(good) >= FUEL_FIT_MIN:
        e = sorted(_fit_estimates(model, good, model["power"]))
        model["max_fuel"], model["fitted"] = round(e[len(e) // 2], 3), True
    # own jumps still to make (not boosted, with the cargo known) before per-hop fuel is known: 0 once it is
    model["need"] = 0 if model["power"] and model["max_fuel"] else \
        max(1, (FUEL_FIT_MIN if model["power"] else FUEL_FIT_POWER_MIN) - len(good))
    return model


def jumps_left(model, fuel, cargo, d=None, cap=1000):
    """(jumps, ly) the fuel takes you, jump after jump, the ship lightening as it burns: at max range (d None) or
    hops of d ly. None without MaxFuelPerJump and p. Past `cap` jumps the rest is counted at the last hop's cost."""
    if not model or not model.get("max_fuel") or not model.get("power") or fuel is None or cargo is None:
        return None
    n, ly = 0, 0.0
    while n < cap:
        mass = model["unladen"] + fuel + cargo
        hop = fsd_range(model, mass) if d is None else min(d, fsd_range(model, mass))
        need = hop_fuel(model, hop, mass)
        if need is None or need <= 0 or need > fuel + 1e-9:
            return n, round(ly, 1)
        fuel, n, ly = fuel - need, n + 1, ly + hop
    more = int(fuel / need)
    return n + more, round(ly + more * hop, 1)



def fleet_figures(ev):
    """A Loadout's figures for the Highway: the ship's masses, tanks and range, and Spansh's exact plotter inputs
    (fuel_power, fuel_multiplier, optimal_mass, max_fuel, supercharge, booster_ly). The power is the fuel model's
    (fsd_power: size 8 = 2.90, the Mk II 2.5025); MaxFuelPerJump and the optimal mass from the drive's engineering
    Modifiers, else its stock figures (FSD_DATA). Those must give the Loadout's own MaxJumpRange (at the unladen mass
    plus one max jump's fuel, as fsd_range has it) to within FSD_RANGE_TOLERANCE; when they don't (a table error, a
    drive variant), the optimal mass that range implies is used instead, so Spansh plans with the range the game
    shows. A MaxJumpRange without the Guardian booster's ly (the booster powered off, or a Loadout written in
    outfitting) is not taken for a table error: the drive's figures stand, and the booster counts only when it is on.
    exact: False when a figure is missing (a drive no table knows): the neutron plotter still works."""
    mods = ev.get("Modules") or []
    fsd_mod = next((m for m in mods if m.get("Slot") == "FrameShiftDrive"), {})
    item = (fsd_mod.get("Item") or "").lower()
    eng = {x.get("Label"): x.get("Value") for x in (fsd_mod.get("Engineering") or {}).get("Modifiers") or []
           if isinstance(x.get("Value"), (int, float)) and not isinstance(x.get("Value"), bool)}
    stock = FSD_DATA.get(re.sub(r"_free$", "", item))
    size = re.search(r"size(\d)", item)
    booster_mod = next((m for m in mods if "guardianfsdbooster" in (m.get("Item") or "").lower()), None)
    booster = re.search(r"size(\d)", (booster_mod or {}).get("Item", "").lower())
    boost = GUARDIAN_BOOST.get(int(booster.group(1)), 0) if booster else 0
    cap = ev.get("FuelCapacity") or {}
    power = fsd_power({"fsd": item, "fsd_size": int(size.group(1)) if size else None})
    max_fuel = eng.get("MaxFuelPerJump") or (stock[1] if stock else None)
    mult = stock[2] if stock else None
    opt = eng.get("FSDOptimalMass") or (stock[0] if stock else None)
    source = "loadout" if eng.get("FSDOptimalMass") else "stock" if opt else None
    r0, unladen = ev.get("MaxJumpRange"), ev.get("UnladenMass")
    if r0 and unladen and max_fuel and mult and power and r0 > boost:
        drive = (max_fuel / mult) ** (1 / power)   # the range at the optimal mass is opt / mass × this
        fits = lambda b: abs((opt / (unladen + max_fuel) * drive + b) / r0 - 1) <= FSD_RANGE_TOLERANCE
        if opt and boost and not fits(boost) and fits(0):
            # MaxJumpRange left the booster out: it was powered off, or the Loadout was written in outfitting. The
            # drive's own figures are right, so keep them. Off: the ship as the game has it, no booster; on: the
            # booster's light years on top of the Loadout's range
            if booster_mod.get("On") is False:
                boost = 0
            else:
                r0 = round(r0 + boost, 3)
        elif not opt or not fits(boost):
            opt, source = round((r0 - boost) * (unladen + max_fuel) / drive, 2), "range"
    out = {"fsd": item, "fsd_size": int(size.group(1)) if size else None, "unladen": unladen, "max_range": r0,
           "fuel_main": cap.get("Main"), "fuel_reserve": cap.get("Reserve"), "cargo_capacity": ev.get("CargoCapacity"),
           "booster_ly": boost, "fuel_power": power, "fuel_multiplier": mult, "optimal_mass": opt, "optimal_source": source,
           "max_fuel": max_fuel,
           "supercharge": fsd_supercharge(item)}
    out["exact"] = all(out.get(k) for k in ("fuel_power", "fuel_multiplier", "optimal_mass", "max_fuel", "unladen", "fuel_main"))
    return out


def fleet_range(fig, cargo=0, fuel=None):
    """A fleet ship's jump range with `cargo` t aboard and the main tank full (or `fuel` t), by the fuel model's
    scaling of its Loadout range; None without the masses."""
    model = fleet_model(fig)
    if not model:
        return None
    return round(fsd_range(model, fig["unladen"] + (fig.get("fuel_main") if fuel is None else fuel or 0) + (cargo or 0)), 2)


def fleet_model(fig):
    """A fleet ship's figures as a fuel model (fsd_range's inputs), or None without the masses."""
    if not fig or not fig.get("unladen") or not fig.get("max_range"):
        return None
    return {"unladen": fig["unladen"], "r0": fig["max_range"], "boost": fig.get("booster_ly") or 0,
            "max_fuel": fig.get("max_fuel"), "power": fig.get("fuel_power")}


def fsd_supercharge(item):
    """A drive's neutron supercharge multiplier: ×6 for the SCO Mk II, ×4 for every other."""
    return FSD_MK2_SUPERCHARGE if "overchargebooster_mkii" in (item or "").lower() else 4


def jump_in_reach(model, d, fuel, other=0.0, mult=1):
    """Whether a d ly jump is in range with `fuel` t in the main tank and `other` t more aboard (cargo, the
    reservoir), the range multiplied by `mult` (a neutron supercharge: the whole range, the booster's ly too)."""
    return fsd_range(model, model["unladen"] + fuel + other, fuel) * mult >= d - 1e-9


def max_fuel_for_jump(model, d, other=0.0, mult=1, cap=None):
    """The most fuel (t in the main tank) with which a d ly jump is still in range (see jump_in_reach), or None when
    no amount reaches it. The range rises with the fuel up to one max jump's worth (below that the fuel limits the
    jump) and falls with the mass past it, so from that peak the answer is found by bisection on fsd_range itself.
    With `cap` (the tank), an answer of cap or more is cap: any fuel the tank holds will do."""
    lo = model.get("max_fuel") or 0.0
    if cap is not None and cap <= lo:   # a tank smaller than one max jump's fuel: its whole is the best there is
        return float(cap) if jump_in_reach(model, d, cap, other, mult) else None
    if not jump_in_reach(model, d, lo, other, mult):
        return None
    hi = cap if cap is not None else lo + 64.0
    if jump_in_reach(model, d, hi, other, mult):
        if cap is not None:
            return float(cap)
        while jump_in_reach(model, d, hi, other, mult):   # no tank given: widen until it no longer reaches
            lo, hi = hi, hi * 2
            if hi > 1e7:
                return hi
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if jump_in_reach(model, d, mid, other, mult) else (lo, mid)
    return lo


FUEL_RUN_MAX_HOPS = 50    # hops fuel_run and fuel_window look ahead at most (the refuel stops of a route come sooner)
FUEL_GRID_STEP = 0.25     # t between two starting fuel levels fuel_window tries


def fuel_run(model, fuel, other, hops):
    """Burn `fuel` t (the main tank) hop by hop, the ship lightening as it goes: `hops` is [(d ly, mult)], mult a
    neutron supercharge or a held jet-cone charge on that hop (1 for none); `other` the t aboard that does not burn
    (cargo, the reservoir). A hop goes when its d / mult is in range at that mass with that fuel (fsd_range, capped
    below one max jump's fuel as target_hop's reach is) and the tank pays its hop_fuel at d / mult. Returns
    (hops_ok, fuel after each of them): hops_ok == len(hops) when the whole run goes. None without MaxFuelPerJump and
    p (no per-hop fuel)."""
    if not model or not model.get("max_fuel") or not model.get("power") or fuel is None:
        return None
    after = []
    for d, mult in hops[:FUEL_RUN_MAX_HOPS]:
        eff = d / (mult or 1)
        mass = model["unladen"] + fuel + (other or 0)
        need = hop_fuel(model, eff, mass)
        if need is None or need > fuel + 1e-9 or eff > fsd_range(model, mass, fuel) + 1e-6:
            break
        fuel -= need
        after.append(fuel)
    return len(after), after


def fuel_window(model, other, hops, tank, step=FUEL_GRID_STEP):
    """The starting fuel (t in the main tank) with which every hop of the run goes: (low, high), or None when no amount
    the tank holds does. The range falls as the mass rises, so a run succeeds on an interval: too little runs dry, too
    much is too heavy for a jump planned at the limit (a full tank may fail where a part one passes). Every `step` t
    from 0 to `tank` is tried (cheap: at most FUEL_RUN_MAX_HOPS hops each), never a bisection over the whole tank, which
    that interval would fool; each end is then refined between its grid point and the failing one beside it. The
    feasible levels are taken as one interval from the lowest to the highest. None without per-hop fuel or a tank."""
    if not tank or tank <= 0 or fuel_run(model, 0.0, other, []) is None:
        return None
    n = len(hops[:FUEL_RUN_MAX_HOPS])

    def goes(f):
        return fuel_run(model, f, other, hops)[0] == n

    grid = [min(tank, k * step) for k in range(int(tank / step) + 1)]
    if grid[-1] < tank:
        grid.append(float(tank))
    ok = [i for i, f in enumerate(grid) if goes(f)]
    if not ok:
        return None

    def edge(good, bad):
        for _ in range(30):
            mid = (good + bad) / 2
            good, bad = (mid, bad) if goes(mid) else (good, mid)
        return good

    lo, hi = grid[ok[0]], grid[ok[-1]]
    if ok[0] > 0:
        lo = edge(lo, grid[ok[0] - 1])
    if ok[-1] < len(grid) - 1:
        hi = edge(hi, grid[ok[-1] + 1])
    return lo, hi


def conservative_range(full, margin, boost=0.0):
    """A range `margin` ly shorter than `full`, never cutting the drive's own part (the booster's ly apart) by more
    than half: the conservative plot's range. A booster at least as long as `full` (a typed range shorter than the
    ship's booster: nonsense) counts as none; the result is never longer than `full`."""
    boost = boost if 0 < boost < full else 0.0
    return min(full, max(full - margin, boost + (full - boost) / 2))


def conservative_optimal_mass(fig, cargo, margin):
    """The exact plotter's figures for a conservative plot: the optimal mass that makes the ship's normal full-tank
    range (cargo aboard) `margin` ly shorter. The range less the booster's ly goes as the optimal mass at every mass
    (fsd_range), so it is scaled by (R - margin - boost) / (R - boost). (optimal mass, R, the shorter R) or None."""
    model = fleet_model(fig)
    if not model or not fig.get("optimal_mass"):
        return None
    b = model["boost"]
    full = fsd_range(model, fig["unladen"] + (fig.get("fuel_main") or 0) + (cargo or 0))
    short = conservative_range(full, margin, b)
    return round(fig["optimal_mass"] * (short - b) / (full - b), 3), full, short
