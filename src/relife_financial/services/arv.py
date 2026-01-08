"""
After Renovation Value (ARV) Service - Business Logic Layer

This module implements the core business logic for property price prediction
after energy renovation using a trained LightGBM model.

Main Functions:
    - predict_arv: Predicts property value based on characteristics and energy class
    - _load_model: Loads the trained LightGBM model (called once at startup)
    - _map_property_type: Maps English labels to Greek labels used by model
    - _build_input_dataframe: Constructs model input features

Dependencies:
    - joblib: For loading the trained model
    - pandas: For input data structuring
    - lgb_model.pkl: Trained LightGBM price prediction model
"""

import joblib
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Optional

from ..models.arv import (
    ARVRequest,
    ARVResponse,
    PropertyType,
)


# ============================================================================
# Module-level model singleton
# ============================================================================

_MODEL = None
_MODEL_PATH = Path(__file__).parent.parent / "data" / "lgb_model.pkl"


def _load_model():
    """
    Load the trained LightGBM model from disk.
    
    This function is called once when the service is first used,
    implementing a lazy-loading singleton pattern.
    
    Returns:
        Trained LightGBM model pipeline
        
    Raises:
        FileNotFoundError: If model file doesn't exist
        Exception: If model loading fails
    """
    global _MODEL
    
    if _MODEL is None:
        if not _MODEL_PATH.exists():
            raise FileNotFoundError(
                f"Model file not found at: {_MODEL_PATH}. "
                "Please ensure lgb_model.pkl is in the data/ directory."
            )
        
        try:
            _MODEL = joblib.load(_MODEL_PATH)
        except Exception as e:
            raise RuntimeError(f"Failed to load model from {_MODEL_PATH}: {e}")
    
    return _MODEL


# ============================================================================
# Property Type Mapping
# ============================================================================

# Mapping from English UI labels to Greek labels used by the trained model
PROPERTY_TYPE_MAP = {
    PropertyType.LOFT: "Loft",
    PropertyType.STUDIO: "Studio / Γκαρσονιέρα",
    PropertyType.VILLA: "Βίλα",
    PropertyType.APARTMENT: "Διαμέρισμα",
    PropertyType.BUILDING: "Κτίριο",
    PropertyType.OTHER: "Λοιπές κατηγορίες",
    PropertyType.MAISONETTE: "Μεζονέτα",
    PropertyType.DETACHED_HOUSE: "Μονοκατοικία",
    PropertyType.APARTMENT_COMPLEX: "Συγκρότημα διαμερισμάτων",
}


def _map_property_type(property_type: PropertyType) -> str:
    """
    Map English property type label to Greek label expected by the model.
    
    Args:
        property_type: PropertyType enum value
        
    Returns:
        Greek label string for model input
        
    Raises:
        ValueError: If property_type is not in mapping (should never happen with enum)
    """
    greek_label = PROPERTY_TYPE_MAP.get(property_type)
    if greek_label is None:
        raise ValueError(f"Unknown property type: {property_type}")
    return greek_label


# ============================================================================
# Input Data Preparation
# ============================================================================

def _build_input_dataframe(request: ARVRequest) -> pd.DataFrame:
    """
    Build a single-row DataFrame with features expected by the trained model.
    
    The model expects these columns:
    - Numeric: floor_area, building_age, floor_number, lat, lng, number_of_floors
    - Categorical: energy_class, type (property type in Greek)
    - Boolean: renovated_last_5_years
    
    Args:
        request: ARVRequest with property characteristics
        
    Returns:
        Single-row DataFrame ready for model.predict()
    """
    # Calculate building age from construction year
    current_year = datetime.now().year
    building_age = current_year - request.construction_year
    
    # Map property type to Greek label
    property_type_greek = _map_property_type(request.property_type)
    
    # Build feature dictionary
    data = {
        # Numeric features
        "floor_area": [request.floor_area],
        "building_age": [building_age],
        "floor_number": [request.floor_number],  # Can be None/NaN
        "lat": [request.lat],
        "lng": [request.lng],
        "number_of_floors": [request.number_of_floors],
        
        # Categorical features
        "energy_class": [request.energy_class.value],  # Use enum value (Greek label)
        "type": [property_type_greek],
        
        # Boolean feature
        "renovated_last_5_years": [request.renovated_last_5_years],
    }
    
    return pd.DataFrame(data)


# ============================================================================
# Main Service Function
# ============================================================================

async def predict_arv(request: ARVRequest) -> ARVResponse:
    """
    Predict After Renovation Value (ARV) for a property.
    
    Orchestrates the ARV prediction workflow:
    1. Loads the trained model (lazy loading on first call)
    2. Prepares input features from request
    3. Runs prediction to get price per square meter
    4. Calculates total property price
    5. Returns structured response with metadata
    
    Args:
        request: ARVRequest containing property characteristics
        
    Returns:
        ARVResponse with predicted prices and metadata
        
    Raises:
        FileNotFoundError: If model file is missing
        RuntimeError: If model loading or prediction fails
        ValueError: If input validation fails
    """
    
    # ─────────────────────────────────────────────────────────────
    # Step 1: Load Model (lazy initialization)
    # ─────────────────────────────────────────────────────────────
    
    try:
        model = _load_model()
    except Exception as e:
        raise RuntimeError(f"Model loading failed: {e}")
    
    # ─────────────────────────────────────────────────────────────
    # Step 2: Prepare Input Features
    # ─────────────────────────────────────────────────────────────
    
    try:
        input_df = _build_input_dataframe(request)
    except Exception as e:
        raise ValueError(f"Failed to build input features: {e}")
    
    # ─────────────────────────────────────────────────────────────
    # Step 3: Run Prediction
    # ─────────────────────────────────────────────────────────────
    
    try:
        # Model predicts price per square meter
        price_per_sqm = model.predict(input_df)[0]
        
        # Calculate total property price
        total_price = price_per_sqm * request.floor_area
        
    except Exception as e:
        raise RuntimeError(f"Prediction failed: {e}")
    
    # ─────────────────────────────────────────────────────────────
    # Step 4: Build Response with Metadata
    # ─────────────────────────────────────────────────────────────
    
    current_year = datetime.now().year
    building_age = current_year - request.construction_year
    
    metadata = {
        "model_file": "lgb_model.pkl",
        "prediction_timestamp": datetime.now().isoformat(),
        "building_age": building_age,
        "property_type_mapped": _map_property_type(request.property_type),
        "input_features": {
            "lat": request.lat,
            "lng": request.lng,
            "floor_area": request.floor_area,
            "building_age": building_age,
            "floor_number": request.floor_number,
            "number_of_floors": request.number_of_floors,
            "energy_class": request.energy_class.value,
            "renovated_last_5_years": request.renovated_last_5_years,
        }
    }
    
    return ARVResponse(
        price_per_sqm=float(price_per_sqm),
        total_price=float(total_price),
        floor_area=request.floor_area,
        energy_class=request.energy_class.value,
        metadata=metadata
    )
