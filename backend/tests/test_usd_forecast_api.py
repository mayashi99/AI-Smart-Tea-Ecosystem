import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from app.api import component04


class UsdForecastApiTests(unittest.TestCase):
    def test_returns_model_comparison_test_predictions_and_forecasts(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory)
            (output_dir / "forecast_metadata.json").write_text(
                json.dumps({"best_model": "ridge"}), encoding="utf-8"
            )
            (output_dir / "model_comparison.csv").write_text(
                "rank,model\n1,ridge\n2,extra_trees\n", encoding="utf-8"
            )
            for model_name in component04.USD_MODEL_NAMES:
                model_dir = output_dir / model_name
                model_dir.mkdir()
                (model_dir / "forecast.csv").write_text(
                    "date,forecast_lkr_per_usd\n2026-10-19,331.0\n",
                    encoding="utf-8",
                )
                (model_dir / "test_predictions.csv").write_text(
                    "date,actual_lkr_per_usd,predicted_lkr_per_usd\n"
                    "2026-10-16,331.2,331.1\n",
                    encoding="utf-8",
                )

            with patch.object(component04, "USD_FORECAST_DIR", output_dir):
                response = component04.get_usd_forecast()

        self.assertEqual(response["metadata"]["best_model"], "ridge")
        self.assertEqual(len(response["model_comparison"]), 2)
        self.assertEqual(response["forecasts"]["ridge"][0]["forecast_lkr_per_usd"], 331.0)
        self.assertEqual(
            response["test_predictions"]["extra_trees"][0]["actual_lkr_per_usd"],
            331.2,
        )

    def test_reports_missing_forecast_outputs(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            with patch.object(
                component04, "USD_FORECAST_DIR", Path(temporary_directory)
            ):
                with self.assertRaises(HTTPException) as error:
                    component04.get_usd_forecast()

        self.assertEqual(error.exception.status_code, 404)
        self.assertIn("Train the USD forecasting models first", error.exception.detail)
