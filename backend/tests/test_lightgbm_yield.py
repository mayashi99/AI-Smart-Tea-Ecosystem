"""Checks for LightGBM inference and held-out evaluation."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd
from app.components.Component02.expected_yield_prediction.lightgbm import predict, evaluate

ROW = dict(Year=2025, Month_Number=1, Week_Number=1, Temperature=23,
           Rainfall_mm=50, Humidity=84, Wind_Speed=3, Solar_Radiation=215,
           Location="Nuwara Eliya", Grown_Type="HIGH grown")


class LightGBMYieldTests(unittest.TestCase):
    def test_prediction_order_and_rounding(self):
        model = Mock()
        model.predict.return_value = [123.456]
        with patch.object(predict, 'load_model', return_value=model):
            self.assertEqual(predict.predict_yield(dict(reversed(list(ROW.items())))), 123.46)
        self.assertEqual(list(model.predict.call_args.args[0].columns), predict.FEATURES)
        model.fit.assert_not_called()

    def test_invalid_inputs(self):
        invalid = [dict(ROW, Year=True), dict(ROW, Month_Number=13), dict(ROW, Week_Number=1.5),
                   dict(ROW, Humidity=101), dict(ROW, Rainfall_mm=-1), dict(ROW, Temperature=np.nan),
                   dict(ROW, Location=''), dict(ROW, Grown_Type='unknown')]
        invalid.append({k: v for k, v in ROW.items() if k != 'Wind_Speed'})
        with patch.object(predict, 'load_model') as loader:
            for row in invalid:
                with self.subTest(row=row), self.assertRaises(ValueError):
                    predict.predict_yield(row)
            loader.assert_not_called()

    def test_missing_model(self):
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(FileNotFoundError):
            predict.load_model(Path(directory) / 'missing.joblib')

    def test_evaluation_zero_targets_and_existing_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            pd.DataFrame([dict(ROW, kg_per_Acre=0), dict(ROW, Week_Number=2, kg_per_Acre=100)]).to_csv(folder / 'test.csv', index=False)
            validation = folder / 'validation_metrics.json'
            validation.write_text('{"existing": true}')
            model = Mock()
            model.predict.return_value = [10, 90]
            with patch.object(evaluate, 'load_model', return_value=model):
                metrics = evaluate.evaluate(folder / 'test.csv', output_dir=folder)
            self.assertEqual(metrics['MAE'], 10)
            self.assertEqual(metrics['MAPE_percent'], 10)
            self.assertEqual(json.loads(validation.read_text()), {'existing': True})
            self.assertEqual(len(pd.read_csv(folder / 'test_predictions_2025.csv')), 2)
            model.fit.assert_not_called()

    def test_non_test_year_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'test.csv'
            pd.DataFrame([dict(ROW, Year=2024, kg_per_Acre=100)]).to_csv(path, index=False)
            with patch.object(evaluate, 'load_model') as loader, self.assertRaises(ValueError):
                evaluate.evaluate(path, output_dir=directory)
            loader.assert_not_called()
