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
    
    This endpoint predicts the property value after energy renovation based on
    physical characteristics, location, and energy performance class. The prediction
    uses a trained LightGBM model on Greek property market data.
    
    **Use Case**: Estimate property value increase due to energy efficiency improvements.
    The energy_class input should be the AFTER renovation EPC label (obtained from
    the energy analysis API).
    
    **Authentication**: Optional. If a valid JWT token is provided, user information
    will be logged for audit purposes.
    
    Parameters
    ----------
    request : ARVRequest
        Property characteristics including:
        - **Location**: lat, lng (coordinates)
        - **Physical**: floor_area (m²), construction_year, floor_number, 
          number_of_floors, property_type
        - **Energy**: energy_class (EPC label after renovation), 
          renovated_last_5_years (typically True)
    
    Returns
    -------
    ARVResponse
        Predicted property value with:
        - price_per_sqm: Predicted price per square meter (€/m²)
        - total_price: Total property value (€)
        - floor_area: Echo of input floor area (m²)
        - energy_class: Echo of input energy class
        - metadata: Additional prediction details (model version, timestamp, etc.)
    
    Raises
    ------
    HTTPException 400
        - Invalid input parameters (e.g., floor_number >= number_of_floors)
        - Missing or invalid property characteristics
    HTTPException 500
        - Model file not found
        - Model loading failed
        - Prediction execution failed
    
    Example Request
    ---------------
    ```json
    {
        "lat": 37.981,
        "lng": 23.728,
        "floor_area": 85.0,
        "construction_year": 1985,
        "floor_number": 2,
        "number_of_floors": 5,
        "property_type": "Apartment",
        "energy_class": "Β+",
        "renovated_last_5_years": true
    }
    ```
    
    Example Response
    ----------------
    ```json
    {
        "price_per_sqm": 1235.50,
        "total_price": 105017.50,
        "floor_area": 85.0,
        "energy_class": "Β+",
        "metadata": {
            "model_file": "lgb_model.pkl",
            "prediction_timestamp": "2026-01-08T14:30:00.123456",
            "building_age": 41,
            "property_type_mapped": "Διαμέρισμα",
            "input_features": {
                "lat": 37.981,
                "lng": 23.728,
                "floor_area": 85.0,
                "building_age": 41,
                "floor_number": 2,
                "number_of_floors": 5,
                "energy_class": "Β+",
                "renovated_last_5_years": true
            }
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
