import unittest

from voidcompass.core.credit_events import authoritative_balance, credit_delta


class CreditEventTests(unittest.TestCase):
    def test_refuel_uses_credit_cost_not_fuel_tonnage(self):
        self.assertEqual(
            credit_delta("RefuelAll", {"Cost": 1122, "Amount": 22.405294}),
            -1122,
        )

    def test_market_buy_and_sell_use_transaction_totals(self):
        self.assertEqual(credit_delta("MarketBuy", {"TotalCost": 5959}), -5959)
        self.assertEqual(credit_delta("MarketSell", {"TotalSale": 84125}), 84125)

    def test_exploration_and_biology_sales_are_credited(self):
        self.assertEqual(
            credit_delta("MultiSellExplorationData", {"TotalEarnings": 4_250_000}),
            4_250_000,
        )
        self.assertEqual(
            credit_delta(
                "SellOrganicData",
                {"BioData": [{"Value": 1_000_000, "Bonus": 4_000_000},
                              {"Value": 2_000_000, "Bonus": 8_000_000}]},
            ),
            15_000_000,
        )

    def test_outfitting_shipyard_and_rebuy_transactions(self):
        self.assertEqual(credit_delta("ModuleSellRemote", {"SellPrice": 75_000}), 75_000)
        self.assertEqual(
            credit_delta("ModuleBuy", {"BuyPrice": 777_600, "SellPrice": 100_000}),
            -677_600,
        )
        self.assertEqual(credit_delta("ShipyardTransfer", {"TransferPrice": 40_095_428}), -40_095_428)
        self.assertEqual(credit_delta("Resurrect", {"Cost": 4_875_368}), -4_875_368)

    def test_odyssey_drones_and_rewards(self):
        self.assertEqual(credit_delta("BuySuit", {"Price": 150_000}), -150_000)
        self.assertEqual(credit_delta("BuyDrones", {"Count": 59, "BuyPrice": 101}), -5959)
        self.assertEqual(credit_delta("SellDrones", {"TotalSale": 300}), 300)
        self.assertEqual(credit_delta("CommunityGoalReward", {"Reward": 20_000_000}), 20_000_000)

    def test_fines_and_bounties_use_schema_amount(self):
        self.assertEqual(credit_delta("PayFines", {"Amount": 12_500}), -12_500)
        self.assertEqual(credit_delta("PayBounties", {"Amount": 345_000}), -345_000)

    def test_carrier_bank_transfer_uses_authoritative_player_balance(self):
        raw = {
            "Deposit": 765_394_119,
            "PlayerBalance": 25_010_000,
            "CarrierBalance": 11_177_236_997,
        }
        self.assertEqual(authoritative_balance(raw), 25_010_000)
        self.assertEqual(credit_delta("CarrierBankTransfer", raw), 0)

    def test_carrier_fuel_and_trade_orders_do_not_change_personal_credits(self):
        self.assertEqual(credit_delta("CarrierDepositFuel", {"Amount": 100}), 0)
        self.assertEqual(credit_delta("CarrierTradeOrder", {"Price": 10_000}), 0)


if __name__ == "__main__":
    unittest.main()
