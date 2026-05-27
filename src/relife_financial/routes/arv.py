"""
After Renovation Value (ARV) API Routes

This module defines the HTTP endpoints for property price prediction
after energy renovation using a trained LightGBM model.

Endpoints:
    POST /arv - Predict property value after renovation
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, status

from relife_financial.auth.dependencies import OptionalAuthenticatedUserDep
from relife_financial.config.logging import get_logger
from relife_financial.config.settings import SettingsDep
from relife_financial.models.arv import (
    ARVRequest,
    ARVResponse,
)
from relife_financial.services.arv import predict_arv

router = APIRouter(tags=["arv"], prefix="/arv")

logger = get_logger(__name__)


@router.post("", response_model=ARVResponse, status_code=status.HTTP_200_OK)
async def calculate_arv(
    request: ARVRequest,
    current_user: OptionalAuthenticatedUserDep,
    settings: SettingsDep,
) -> ARVResponse:
    """
    Calculate After Renovation Value (ARV) for a property.

    Predicts property market value using a trained LightGBM model on Greek
    property market data. Accepts post-renovation energy consumption (required)
    and optionally pre-renovation energy consumption to compute the value uplift.

    **EPC Resolution Chain** (applied to each consumption value):
    energy_consumption → source-country EPC → Italy EPC → Greek EPC → model

    **Authentication**: Optional. If a valid JWT token is provided, user information
    will be logged for audit purposes.

    Parameters
    ----------
    request : ARVRequest
        Property characteristics including:
        - **Location**: lat, lng (coordinates)
        - **Physical**: floor_area (m²), construction_year, floor_number,
          number_of_floors, property_type
        - **Energy**: target_country, energy_consumption_after (required),
          energy_consumption_before (optional), renovated_last_5_years

    Returns
    -------
    ARVResponse
        - after: predicted value at post-renovation energy consumption (always present)
        - before: predicted value at pre-renovation energy consumption (only when energy_consumption_before is provided)
        - uplift: price_increase (€) and price_increase_pct (%) (only when before is present)
        - floor_area: echo of input floor area (m²)
        - metadata: model file, timestamp, building age, input echo

    Raises
    ------
    HTTPException 400
        - Unknown target_country
        - floor_number >= number_of_floors
        - EPC mapping failure
    HTTPException 500
        - Model file not found or loading failed
        - Prediction execution failed

    Example Request (with before/after comparison)
    -----------------------------------------------
    ```json
    {
        "lat": 37.981,
        "lng": 23.728,
        "floor_area": 85.0,
        "construction_year": 1985,
        "floor_number": 2,
        "number_of_floors": 5,
        "property_type": "Apartment",
        "target_country": "Italy",
        "energy_consumption_before": 220.0,
        "energy_consumption_after": 85.0,
        "renovated_last_5_years": true
    }
    ```

    Example Response
    ----------------
    ```json
    {
        "after": {
            "price_per_sqm": 1235.50,
            "total_price": 105017.50,
            "greek_epc_class": "Ε",
            "epc_resolution": {"target_country": "Italy", "source_epc_class": "E", "italy_epc_class": "E", "greek_epc_class": "Ε"}
        },
        "before": {
            "price_per_sqm": 980.00,
            "total_price": 83300.00,
            "greek_epc_class": "Η",
            "epc_resolution": {"target_country": "Italy", "source_epc_class": "G", "italy_epc_class": "G", "greek_epc_class": "Η"}
        },
        "uplift": {
            "price_increase": 21717.50,
            "price_increase_pct": 26.07
        },
        "floor_area": 85.0,
        "metadata": {
            "model_file": "lgb_model_greece.pkl",
            "prediction_timestamp": "2026-01-08T14:30:00.123456",
            "building_age": 41,
            "energy_consumption_unit": "kWh/m²/year"
        }
    }
    ```
    
    Notes
    -----
    - The model expects Greek EPC labels: Η, Ζ, Ε, Δ, Γ, Β, Β+, Α, Α+
    - Property types are mapped to Greek labels internally
    - The model is loaded once and cached for performance
    - Building age is calculated automatically from construction_year
    - For before/after comparison: call endpoint twice with different energy_class values
    """
    
    user_id = current_user.user_id if current_user else "anonymous"
    
    logger.info(
        f"ARV prediction requested by user {user_id}",
        extra={
            "user_id": user_id,
            "floor_area": request.floor_area,
            "energy_class": request.energy_class.value,
            "property_type": request.property_type.value,
        }
    )
    
    try:
        result = await predict_arv(request)
        
        logger.info(
            f"ARV prediction successful for user {user_id}",
            extra={
                "user_id": user_id,
                "price_per_sqm": result.price_per_sqm,
                "total_price": result.total_price,
            }
        )
        
        return result
        
    except FileNotFoundError as e:
        logger.error(
            f"Model file not found: {e}",
            extra={"user_id": user_id}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ARV model not available. Please contact system administrator."
        )
        
    except ValueError as e:
        logger.warning(
            f"Invalid input for ARV prediction: {e}",
            extra={"user_id": user_id}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid input parameters: {str(e)}"
        )
        
    except RuntimeError as e:
        logger.error(
            f"ARV prediction failed: {e}",
            extra={"user_id": user_id}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Property valuation failed. Please try again later."
        )
        
    except Exception as e:
        logger.error(
            f"Unexpected error in ARV prediction: {e}",
            extra={"user_id": user_id},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during property valuation."
        )
