"""Explainable zone quality scoring using auction evidence and declared indicators."""
from pathlib import Path

import pandas as pd


DATA_DIR = Path(__file__).resolve().parents[3] / "ml" / "datasets" / "processed" / "component04"
AUCTION_FILE = DATA_DIR / "auction_price_clean.csv"
ZONE_NAMES = ("High Growns", "Medium Growns", "Low Growns")
WEIGHTS = {
    "auction_price": 35,
    "export_success_rate": 25,
    "buyer_preference": 20,
    "historical_demand": 10,
    "climate_suitability": 10,
}


def get_zone_intelligence_data() -> dict:
    if not AUCTION_FILE.exists():
        raise FileNotFoundError("Prepare the auction price dataset before loading zone intelligence.")
    frame = pd.read_csv(AUCTION_FILE, parse_dates=["auction_date"])
    frame = frame[frame["growing_zone"].isin(ZONE_NAMES)].copy()
    frame = frame.dropna(subset=["auction_date", "quantity_kg", "avg_price_lkr"])
    months = sorted(frame["auction_date"].dt.to_period("M").unique())
    if len(months) < 2:
        raise ValueError("At least two months of auction zone data are required.")
    recent_months = months[-12:]
    previous_months = months[-24:-12]
    recent = frame[frame["auction_date"].dt.to_period("M").isin(recent_months)]
    previous = frame[frame["auction_date"].dt.to_period("M").isin(previous_months)]

    raw = {}
    for zone in ZONE_NAMES:
        current = recent[recent["growing_zone"].eq(zone)]
        prior = previous[previous["growing_zone"].eq(zone)]
        current_volume = float(current["quantity_kg"].sum())
        prior_volume = float(prior["quantity_kg"].sum())
        weighted_price = (
            float((current["avg_price_lkr"] * current["quantity_kg"]).sum() / current_volume)
            if current_volume > 0 else float(current["avg_price_lkr"].mean()) if not current.empty else 0.0
        )
        demand_change_pct = (current_volume / prior_volume - 1) * 100 if prior_volume > 0 else None
        raw[zone] = {
            "auction_price_lkr": weighted_price,
            "recent_volume_kg": current_volume,
            "previous_volume_kg": prior_volume,
            "demand_change_pct": demand_change_pct,
        }

    prices = [item["auction_price_lkr"] for item in raw.values()]
    price_min, price_max = min(prices), max(prices)
    total_volume = sum(item["recent_volume_kg"] for item in raw.values())
    latest_period = str(max(months))
    previous_period = str(months[-24]) if len(months) >= 24 else str(months[0])

    zones = []
    for zone in ZONE_NAMES:
        item = raw[zone]
        share = item["recent_volume_kg"] / total_volume if total_volume else 0
        if price_max == price_min:
            price_score = 50.0
        else:
            price_score = (item["auction_price_lkr"] - price_min) / (price_max - price_min) * 100
        change = item["demand_change_pct"]
        demand_score = max(0.0, min(100.0, 50.0 + change)) if change is not None else 50.0
        zones.append({
            "zone": zone,
            "auction_price_lkr": round(item["auction_price_lkr"], 2),
            "auction_price_score": round(price_score, 1),
            "recent_auction_volume_kg": round(item["recent_volume_kg"], 2),
            "buyer_preference_score": round(share * 100, 1),
            "buyer_preference_share_pct": round(share * 100, 1),
            "historical_demand_change_pct": round(change, 1) if change is not None else None,
            "historical_demand_score": round(demand_score, 1),
            "latest_period": latest_period,
            "comparison_period_start": previous_period,
        })
    return {
        "zones": zones,
        "weights": WEIGHTS,
        "data_note": "Auction price and quantity are calculated from the latest available zone-level auction records. Quantity share is used as a buyer-preference proxy; it is not a direct buyer survey. Climate suitability and export success rate are not present in the supplied datasets and must be entered with supporting evidence.",
    }


def calculate_zone_quality(zone: str, climate_suitability: float, export_success_rate: float,
                           climate_evidence: str | None = None,
                           export_success_evidence: str | None = None) -> dict:
    data = get_zone_intelligence_data()
    selected = next((item for item in data["zones"] if item["zone"] == zone), None)
    if selected is None:
        raise ValueError(f"Unsupported growing zone: {zone}")

    factors = [
        {"key": "auction_price", "label": "Auction Price", "weight": WEIGHTS["auction_price"],
         "score": selected["auction_price_score"], "value": f"LKR {selected['auction_price_lkr']:,.2f}/kg",
         "source": "Quantity-weighted mean from latest zone auction records; normalized across the three growing zones."},
        {"key": "export_success_rate", "label": "Export Success Rate", "weight": WEIGHTS["export_success_rate"],
         "score": export_success_rate, "value": f"{export_success_rate:.1f}%",
         "source": export_success_evidence or "User-provided score; add the period or source used."},
        {"key": "buyer_preference", "label": "Buyer Preference", "weight": WEIGHTS["buyer_preference"],
         "score": selected["buyer_preference_score"], "value": f"{selected['buyer_preference_share_pct']:.1f}% of recent auction quantity",
         "source": "Recent auction quantity share used as a market preference proxy; this is not direct buyer survey data."},
        {"key": "historical_demand", "label": "Historical Demand", "weight": WEIGHTS["historical_demand"],
         "score": selected["historical_demand_score"],
         "value": f"{selected['historical_demand_change_pct']:+.1f}% auction quantity change" if selected["historical_demand_change_pct"] is not None else "Not enough comparison history",
         "source": f"Recent auction quantity versus the preceding period, through {selected['latest_period']}."},
        {"key": "climate_suitability", "label": "Climate Suitability", "weight": WEIGHTS["climate_suitability"],
         "score": climate_suitability, "value": f"{climate_suitability:.1f}/100",
         "source": climate_evidence or "User-provided score; add the climate source or assessment used."},
    ]
    score = round(sum(factor["score"] * factor["weight"] for factor in factors) / 100, 1)
    band = "Excellent" if score >= 80 else "Strong" if score >= 65 else "Developing" if score >= 50 else "Needs improvement"
    weakest = sorted(factors, key=lambda factor: factor["score"])[:2]
    recommendation = (
        f"{zone} has a zone quality score of {score:.1f}/100 ({band}). Prioritize improvements in "
        f"{weakest[0]['label'].lower()} and {weakest[1]['label'].lower()}, and validate the declared climate and export-success evidence before selecting this zone for an export plan."
    )
    return {
        "zone": zone,
        "quality_score": score,
        "band": band,
        "weights": WEIGHTS,
        "factors": factors,
        "recommendation": recommendation,
        "data_note": data["data_note"],
    }
