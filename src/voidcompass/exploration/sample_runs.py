"""My Samples (5.7.8): every sample run from the journal, with its species,
body, value and what became of it: aboard, sold or lost. Pure: hand it the
events (journal_events.read with EVENTS)."""

from __future__ import annotations

from voidcompass.exploration import bio_values, journal_events

EVENTS = frozenset({"ScanOrganic", "SellOrganicData", "Died", "FSDJump", "Location", "CarrierJump", "FSSBodySignals", "SAASignalsFound",
                    "Touchdown", "ApproachBody", "Disembark", "Resurrect"})
journal_events.register(EVENTS)


def runs(events):
    """[{system, body, species, variant, genus, started, analysed, state, value, sold_at, sold_for}] newest first."""
    systems, bodies = {}, {}
    out, open_runs = [], {}
    for raw in events:
        event = raw.get("event")
        stamp = str(raw.get("timestamp") or "")
        if event in ("FSDJump", "Location", "CarrierJump") and raw.get("SystemAddress") is not None:
            systems[raw["SystemAddress"]] = raw.get("StarSystem") or ""
        elif event in ("FSSBodySignals", "SAASignalsFound") and raw.get("BodyID") is not None:
            bodies[(raw.get("SystemAddress"), raw["BodyID"])] = raw.get("BodyName") or ""
        elif event in ("Touchdown", "ApproachBody", "Disembark") and raw.get("BodyID") is not None and raw.get("Body"):
            bodies[(raw.get("SystemAddress"), raw["BodyID"])] = raw.get("Body") or ""
        elif event == "ScanOrganic":
            key = (raw.get("SystemAddress"), raw.get("Body"), raw.get("Species"))
            kind = raw.get("ScanType")
            species = raw.get("Species_Localised") or raw.get("Species") or ""
            run = open_runs.get(key)
            if run is None or kind == "Log":
                run = {"system": systems.get(raw.get("SystemAddress"), ""),
                       "body": bodies.get((raw.get("SystemAddress"), raw.get("Body")), ""),
                       "species": species, "variant": raw.get("Variant_Localised") or "",
                       "genus": raw.get("Genus_Localised") or "", "started": stamp, "analysed": None,
                       "samples": 0, "state": "sampling", "value": bio_values.species_value(species) or 0,
                       "sold_at": None, "sold_for": None}
                open_runs[key] = run
                out.append(run)
            run["samples"] = min(3, run["samples"] + 1)
            if kind == "Analyse":
                run.update(analysed=stamp, samples=3, state="aboard")
                open_runs.pop(key, None)
        elif event == "SellOrganicData":
            for sale in raw.get("BioData") or ():
                species = sale.get("Species_Localised") or sale.get("Species") or ""
                match = next((run for run in out if run["state"] == "aboard" and run["species"] == species), None)
                if match:
                    match.update(state="sold", sold_at=stamp,
                                 sold_for=int(sale.get("Value") or 0) + int(sale.get("Bonus") or 0))
        elif event == "Died":
            for run in out:
                if run["state"] in ("aboard", "sampling"):
                    run.update(state="lost", sold_at=stamp)
            open_runs.clear()
    out.reverse()
    return out
