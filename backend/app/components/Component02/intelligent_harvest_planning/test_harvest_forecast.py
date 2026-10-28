from datetime import date, datetime
import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException
import requests

from app.components.Component02.intelligent_harvest_planning.harvest_forecast import compare_forecast, harvest_forecast


def payload(**overrides):
    return {"daily": {
        "time": ["2026-10-15", "2026-10-16", "2026-10-17"],
        "precipitation_sum": [3, 0, 5],
        "precipitation_probability_max": [70, 10, 90],
        "temperature_2m_min": [20, 21, 20],
        "temperature_2m_max": [28, 27, 29],
        "wind_speed_10m_max": [3, 2, 4],
        "weather_code": [61, 1, 63],
        **overrides,
    }}


class HarvestForecastTests(unittest.TestCase):
    today = date(2026, 10, 14)

    def test_selects_driest_day_and_preserves_three_forecast_days(self):
        result = compare_forecast(payload(), self.today)
        self.assertEqual(result["best_date"], "2026-10-16")
        self.assertEqual(len(result["days"]), 3)
        self.assertEqual(result["days"][1]["rainfall_mm"], 0)

    def test_excludes_thunderstorms_even_when_rainfall_is_lower(self):
        result = compare_forecast(payload(weather_code=[61, 95, 63]), self.today)
        self.assertEqual(result["best_date"], "2026-10-15")
        self.assertTrue(result["cautions"])

    def test_does_not_recommend_when_all_days_have_thunderstorms(self):
        result = compare_forecast(payload(weather_code=[95, 96, 99]), self.today)
        self.assertIsNone(result["best_date"])
        self.assertEqual(result["status"], "unfavourable")

    def test_partial_null_and_invalid_values_do_not_produce_recommendation(self):
        for changes in [
            {"precipitation_sum": [3, None, 5]},
            {"time": ["2026-10-15", "2026-10-16"]},
            {"wind_speed_10m_max": [3, float("nan"), 4]},
            {"precipitation_probability_max": [20, 101, 90]},
            {"temperature_2m_min": [30, 21, 20]},
        ]:
            with self.subTest(changes=changes):
                result = compare_forecast(payload(**changes), self.today)
                self.assertIsNone(result["best_date"])
                self.assertEqual(result["status"], "incomplete")

    def test_rain_probability_then_wind_then_heat_break_ties(self):
        common = {"precipitation_sum": [0, 0, 0], "precipitation_probability_max": [10, 10, 10]}
        result = compare_forecast(payload(**common, wind_speed_10m_max=[1, 2, 3]), self.today)
        self.assertEqual(result["best_date"], "2026-10-15")
        result = compare_forecast(payload(**common, wind_speed_10m_max=[2, 2, 2]), self.today)
        self.assertEqual(result["best_date"], "2026-10-16")
        common["precipitation_probability_max"] = [10, 20, 30]
        result = compare_forecast(payload(**common), self.today)
        self.assertEqual(result["best_date"], "2026-10-15")

    def test_equal_weather_prefers_earlier_day(self):
        data = payload()
        for key, values in data["daily"].items():
            if key != "time":
                data["daily"][key] = [values[0]] * 3
        self.assertEqual(compare_forecast(data, self.today)["best_date"], "2026-10-15")

    def test_forecast_window_crosses_year_boundary_and_ignores_today(self):
        result = compare_forecast({"daily": {}}, date(2026, 12, 31))
        self.assertEqual([day["date"] for day in result["days"]], ["2027-01-01", "2027-01-02", "2027-01-03"])
        self.assertIsNone(result["best_date"])

    @patch("app.components.Component02.intelligent_harvest_planning.harvest_forecast.requests.get")
    @patch("app.components.Component02.intelligent_harvest_planning.harvest_forecast.datetime")
    def test_provider_request_uses_local_next_three_days_and_correct_units(self, clock, get):
        clock.now.return_value = datetime(2026, 10, 14, 10, 0)
        get.return_value = Mock(json=lambda: payload())
        result = harvest_forecast(6.0341, 80.2155)
        params = get.call_args.kwargs["params"]
        self.assertEqual(params["start_date"], "2026-10-15")
        self.assertEqual(params["end_date"], "2026-10-17")
        self.assertEqual(params["timezone"], "Asia/Colombo")
        self.assertEqual(params["wind_speed_unit"], "ms")
        self.assertEqual(result["best_date"], "2026-10-16")

    @patch("app.components.Component02.intelligent_harvest_planning.harvest_forecast.requests.get", side_effect=requests.Timeout)
    def test_network_failure_is_reported_without_fabricating_forecast(self, get):
        with self.assertRaises(HTTPException) as caught:
            harvest_forecast(6.0341, 80.2155)
        self.assertEqual(caught.exception.status_code, 502)


if __name__ == "__main__":
    unittest.main()
