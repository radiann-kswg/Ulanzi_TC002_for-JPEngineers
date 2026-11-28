from datetime import date, datetime, timezone
import unittest

from bridge import holiday_calendar


class HolidayCalendarTests(unittest.TestCase):
    def test_japan_and_representative_offsets_are_generated(self):
        calls = []
        def japan():
            return [(date(2026, 1, 1), "元日")]
        def world(country, year):
            calls.append((country, year))
            return [(date(year, 1, 1), "New Year's Day")]

        now = int(datetime(2026, 6, 1, tzinfo=timezone.utc).timestamp())
        rows = holiday_calendar.collect(now, japan, world)["holidays"]
        self.assertIn({"date":"2026-01-01","offset":540,"region":"日本","name":"元日"}, rows)
        self.assertIn({"date":"2026-01-01","offset":-300,"region":"US","name":"New Year's Day"}, rows)
        self.assertEqual(sum(country == "US" for country, _ in calls), 1)
        self.assertNotIn(("JP", 2026), calls)

    def test_world_loader_returns_dates_and_names(self):
        rows = holiday_calendar.world_holidays("US", 2026)
        self.assertTrue(rows)
        self.assertTrue(all(isinstance(day, date) and name for day, name in rows))

    def test_world_failure_keeps_japanese_holidays(self):
        def world(country, year):
            raise OSError("offline")
        result = holiday_calendar.collect(
            int(datetime(2026, 6, 1, tzinfo=timezone.utc).timestamp()),
            lambda: [(date(2026, 1, 1), "元日")], world)
        self.assertIn({"date":"2026-01-01","offset":540,"region":"日本","name":"元日"},
                      result["holidays"])
        self.assertTrue(result["worldErrors"])

    def test_local_new_year_requests_both_years(self):
        years_seen = []
        def world(country, year):
            years_seen.append(year)
            return []
        now = int(datetime(2026, 12, 31, 12, tzinfo=timezone.utc).timestamp())
        holiday_calendar.collect(now, lambda: [], world)
        self.assertEqual(set(years_seen), {2026, 2027})


if __name__ == "__main__":
    unittest.main()
