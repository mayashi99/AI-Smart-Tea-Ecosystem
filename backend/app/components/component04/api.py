"""
Component 04: Export Intelligence & Price/Demand Forecasting API Router.
Note: Tea Grade Classification & Purity Analysis belong to Component 03 in app.components.component3.
"""

import logging
from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/component04",
    tags=["Component 04: Export Intelligence & Price/Demand Forecasting"],
)


@router.get("/health")
def check_health():
    """
    Health check endpoint for Component 04.
    """
    return {
        "status": "online",
        "service": "Component 04: Export Intelligence & Price/Demand Forecasting",
        "active_modules": [
            "export_advisor",
            "demand_forecasting",
            "auction_price_forecasting",
        ],
    }


@router.get("/info")
def get_info():
    """
    Diagnostic information for Component 04.
    """
    return {
        "component": "Component 04: Export Intelligence & Price/Demand Forecasting",
        "status": "active",
        "modules": {
            "export_advisor": "Heuristic & Multi-variable export planning",
            "export_demand": "LSTM Neural Network demand forecasting",
            "auction_price": "Combined auction price forecasting",
        },
    }
