import unittest
from dataclasses import replace
from datetime import datetime, timezone, timedelta
from private_futures.risk_guard import AccountSnapshot, Candidate, Policy, check

class PrivateFuturesRiskTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 9, 18, tzinfo=timezone.utc)
        self.account = AccountSnapshot(self.now, 0, 0, 0, 30, True, True, True)
        self.trade = Candidate("NNQ", "LONG", 100, 95, 108, 1, 0.5, self.now)
    def test_valid_simulation(self):
        self.assertEqual(check(self.trade, self.account, now=self.now), (True, "SIMULATION_ONLY"))
    def test_live_rejected(self):
        self.assertEqual(check(self.trade, replace(self.account, simulation_account=False), now=self.now)[1], "LIVE_ACCOUNT_FORBIDDEN")
    def test_stale_feed_and_account_rejected(self):
        self.assertEqual(check(replace(self.trade, market_data_at=self.now-timedelta(seconds=4)), self.account, now=self.now)[1], "STALE_QUOTE")
        self.assertEqual(check(self.trade, replace(self.account,timestamp=self.now-timedelta(seconds=16)), now=self.now)[1], "STALE_ACCOUNT")
    def test_max_contracts_and_positions(self):
        self.assertEqual(check(replace(self.trade,qty=2),self.account,now=self.now)[1],"POSITION_SIZE_REJECTED")
        self.assertEqual(check(self.trade,replace(self.account,open_positions=1),now=self.now)[1],"POSITION_LIMIT")
    def test_risk_and_rr_guards(self):
        self.assertEqual(check(replace(self.trade,stop=80),self.account,now=self.now)[1],"PER_TRADE_RISK_LIMIT")
        self.assertEqual(check(replace(self.trade,target=105),self.account,now=self.now)[1],"INVALID_REWARD_RISK")
    def test_daily_guard_and_protection(self):
        self.assertEqual(check(self.trade,replace(self.account,realized_today_usd=-8),now=self.now)[1],"DAILY_LOSS_GUARD")
        self.assertEqual(check(self.trade,replace(self.account,protective_order_system_ok=False),now=self.now)[1],"CONNECTION_OR_PROTECTION_UNAVAILABLE")
    def test_wrong_symbol(self):
        self.assertEqual(check(replace(self.trade,symbol="NQ"),self.account,now=self.now)[1],"SYMBOL_NOT_APPROVED")

if __name__ == "__main__":
    unittest.main()
