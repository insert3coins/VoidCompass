"""Pure Elite journal credit accounting helpers.

Only events that immediately change the commander's personal balance belong
here. Carrier operating balances and trade orders are deliberately excluded.
"""


def _money(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def authoritative_balance(raw):
    """Return an explicit post-event commander balance when Elite supplies it."""
    if not isinstance(raw, dict):
        return None
    for key in ("Credits", "Balance", "PlayerBalance"):
        if raw.get(key) is not None:
            try:
                return int(raw[key])
            except (TypeError, ValueError):
                return None
    return None


def credit_delta(event, raw):
    """Return the immediate personal-credit delta for a journal event."""
    if not isinstance(raw, dict):
        return 0
    event = str(event or "")

    if event == "MarketBuy":
        return -_money(raw.get("TotalCost") or _money(raw.get("BuyPrice") or raw.get("Price")) * _money(raw.get("Count")))
    if event == "MarketSell":
        return _money(raw.get("TotalSale") or _money(raw.get("SellPrice") or raw.get("Price")) * _money(raw.get("Count")))

    if event == "SellOrganicData":
        total = _money(raw.get("TotalSale") or raw.get("TotalValue"))
        if total:
            return total
        return sum(
            _money(sample.get("Value")) + _money(sample.get("Bonus"))
            for sample in (raw.get("BioData") or ())
            if isinstance(sample, dict)
        )

    positive_amount = {
        "RedeemVoucher", "SellExplorationData", "MultiSellExplorationData",
        "PowerplaySalary",
    }
    if event in positive_amount:
        return _money(
            raw.get("Amount") or raw.get("TotalEarnings")
            or raw.get("TotalSale") or raw.get("Reward")
        )

    if event in {"MissionCompleted", "CommunityGoalReward", "SearchAndRescue"}:
        return _money(raw.get("Reward"))
    if event in {"CancelTaxi", "CancelDropship"}:
        return _money(raw.get("Refund"))
    if event in {"SellDrones"}:
        return _money(raw.get("TotalSale") or _money(raw.get("SellPrice")) * _money(raw.get("Count")))
    if event in {"SellSuit", "SellWeapon", "SellMicroResources"}:
        return _money(raw.get("Price"))
    if event in {"ModuleSell", "ModuleSellRemote"}:
        return _money(raw.get("SellPrice"))
    if event in {"ShipyardSell", "SellShipOnRebuy"}:
        return _money(raw.get("ShipPrice") or raw.get("SellPrice"))
    if event in {"PayFines", "PayBounties", "PayLegacyFines"}:
        return -_money(raw.get("Amount") or raw.get("Cost"))

    negative_cost = {
        "BuyExplorationData", "BuyTradeData",
        "RefuelAll", "RefuelPartial", "Repair", "RepairAll", "BuyAmmo",
        "RestockVehicle", "Resurrect", "CrewHire",
        "BookTaxi", "BookDropship", "UpgradeSuit", "UpgradeWeapon",
        "ModuleRetrieve", "PowerplayFastTrack",
    }
    if event in negative_cost:
        # Cost is credits; Amount on Refuel events is tonnes of fuel.
        return -_money(raw.get("Cost"))
    if event == "BuyDrones":
        return -_money(raw.get("TotalCost") or _money(raw.get("BuyPrice")) * _money(raw.get("Count")))
    if event in {"BuySuit", "BuyWeapon", "BuyMicroResources"}:
        return -_money(raw.get("Price"))
    if event == "ShipyardTransfer":
        return -_money(raw.get("TransferPrice"))
    if event == "CarrierBuy":
        return -_money(raw.get("Price"))
    if event == "EngineerContribution" and str(raw.get("Type") or "").casefold() == "credits":
        return -_money(raw.get("Quantity"))

    # Buying may include an immediate trade-in of the replaced module/ship.
    if event == "ModuleBuy":
        return -_money(raw.get("BuyPrice")) + _money(raw.get("SellPrice"))
    if event == "ShipyardBuy":
        return -_money(raw.get("ShipPrice") or raw.get("BuyPrice")) + _money(raw.get("SellPrice"))
    if event == "ShipyardSwap":
        return _money(raw.get("SellPrice"))

    return 0
