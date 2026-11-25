import unittest

from bridge import claude_desktop, desktop, github


class UsageSourcesTest(unittest.TestCase):
    def test_copilot_uses_account_reset_and_metered_overage(self):
        account = {"quota_reset_date_utc": "2026-12-01T00:00:00.000Z",
                   "token_based_billing": True, "quota_snapshots": {"premium_interactions": {
                       "percent_remaining": 0, "quota_reset_at": 0, "overage_count": 3,
                       "entitlement": 100, "unlimited": False}}}
        data = github.copilot_quota(account)
        self.assertEqual(data["fields"], {"0.left": "0%", "0.creditUsed": "3 cr"})
        self.assertEqual(data["resets"], {"": 1796083200})
        account["token_based_billing"]=False
        self.assertNotIn("0.creditUsed",github.copilot_quota(account)["fields"])

    def test_claude_live_plan_has_deadline_even_when_desktop_history_does_not(self):
        raw = {"rate_limits_available": True, "rate_limits": {"five_hour": None,
               "seven_day": {"utilization": 51, "resets_at": "2026-12-01T00:00:00+00:00"}}}
        data = claude_desktop.plan_limits(raw)
        self.assertEqual(data, {"fields": {"1.left": "7d 49%"}, "resets": {"7d": 1796083200}})

    def test_codex_monthly_debits_include_only_current_period(self):
        now=1795579200
        rows=[{"date":"2026-10-31","credit_amount":50},{"date":"2026-11-11","credit_amount":"2.15"},
              {"date":"2026-11-13","premium_usage_values":{"credit_usage_credits":{"cli":1,"work":0.5}},
               "models":[{"on_demand_credits":1.5}]},{"date":"2026-11-14","models":[{"on_demand_credits":0.25}]}]
        report=desktop.personal_credit_usage({"data":rows},now)
        self.assertEqual(report,{"fields":{"2.creditUsed":"3.90 cr"},"periodBounds":[1793491200,1796083200]})
        self.assertEqual(desktop.personal_credit_usage({"data":[]},now)["fields"]["2.creditUsed"],"0 cr")
        for bad in ({"data":[],"has_more":True},{"data":[{"date":"2026-11-10","balance":"0"}]}):
            with self.assertRaises(ValueError):
                desktop.personal_credit_usage(bad,now)
