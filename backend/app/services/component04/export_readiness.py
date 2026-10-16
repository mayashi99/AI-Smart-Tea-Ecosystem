"""Explainable Export Readiness Index based on forecast evidence and exporter inputs."""
import json
from pathlib import Path

import pandas as pd


DATA_DIR = Path(__file__).resolve().parents[3] / "ml" / "datasets" / "processed" / "component04"


def calculate_export_readiness(payload: dict) -> dict:
    metrics_path = DATA_DIR / "export_demand_metrics.json"
    forecast_path = DATA_DIR / "export_demand_forecast.csv"
    history_path = DATA_DIR / "export_demand_monthly.csv"
    if not all(path.exists() for path in (metrics_path, forecast_path, history_path)):
        raise FileNotFoundError("Train the export-demand forecast before calculating ERI.")

    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    forecast = pd.read_csv(forecast_path)
    history = pd.read_csv(history_path)
    forecast_total = float(forecast["forecast_export_volume_kg"].sum())
    latest_year = history.tail(12)
    recent_total = float(latest_year["export_volume_kg"].sum())
    trend_pct = ((forecast_total - recent_total) / recent_total * 100) if recent_total else 0.0
    mape = float(metrics.get("mape", 100))

    criteria = [
        {"key": "demand_outlook", "label": "Demand outlook", "weight": 25,
         "score": 80 if trend_pct >= 0 else max(35, 80 + trend_pct * 1.5),
         "evidence": f"12-month forecast is {trend_pct:+.1f}% versus the latest 12 observed months."},
        {"key": "forecast_confidence", "label": "Forecast confidence", "weight": 25,
         "score": max(0, min(100, 100 - mape * 2)),
         "evidence": f"Historical holdout MAPE is {mape:.2f}%. This is a national aggregate forecast."},
        {"key": "supply_capacity", "label": "Supply capacity", "weight": 20,
         "score": min(100, payload["monthly_capacity_tonnes"] / max(forecast_total / 12 / 1000, 1) * 100),
         "evidence": f"Declared monthly capacity: {payload['monthly_capacity_tonnes']:,.1f} tonnes."},
        {"key": "documentation", "label": "Export documentation", "weight": 20,
         "score": sum(payload["documents"].values()) / max(1, len(payload["documents"])) * 100,
         "evidence": f"{sum(payload['documents'].values())} of {len(payload['documents'])} declared document checks are ready."},
        {"key": "quality_controls", "label": "Quality controls", "weight": 10,
         "score": 100 if payload["quality_controls_ready"] else 25,
         "evidence": "Quality control readiness was declared by the user."},
    ]
    score = round(sum(item["score"] * item["weight"] for item in criteria) / 100)
    band = "Ready" if score >= 80 else "Nearly ready" if score >= 60 else "Preparation needed"
    recommendations = []
    for item in criteria:
        if item["score"] < 70:
            action = {
                "demand_outlook": "Review the destination and product mix against this aggregate demand outlook.",
                "forecast_confidence": "Use a conservative shipment plan and refresh the forecast as new monthly data arrives.",
                "supply_capacity": "Confirm committed supply and shipment capacity before accepting export volume.",
                "documentation": "Complete the missing documentation checks with your export compliance team.",
                "quality_controls": "Confirm product quality checks and batch inspection records before shipment.",
            }[item["key"]]
            recommendations.append({"criterion": item["label"], "action": action, "evidence": item["evidence"]})
    if not recommendations:
        recommendations.append({"criterion": "Maintain readiness", "action": "Recheck capacity, documentation, and quality controls for each shipment.", "evidence": "All scored criteria are currently at or above 70."})
    return {
        "index_name": "Export Readiness Index (ERI)", "score": score, "band": band,
        "destination_country": payload.get("destination_country") or "Not specified",
        "criteria": criteria, "recommendations": recommendations,
        "forecast_context": {"model": metrics.get("model"), "holdout_mape_pct": mape,
                             "forecast_12_months_kg": round(forecast_total),
                             "latest_12_months_actual_kg": round(recent_total),
                             "forecast_change_pct": round(trend_pct, 2)},
        "method_note": "Explainable, rules-based index using model evidence and user-declared readiness inputs; not an official certification or destination-specific regulatory assessment.",
    }
