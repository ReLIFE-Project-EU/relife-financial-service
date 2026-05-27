"""
After Renovation Value (ARV) Service - Business Logic Layer

This module implements the core business logic for property price prediction
after energy renovation using a trained LightGBM model.

EPC Resolution Chain (Logic 2):
    energy_consumption (kWh/m²/year or % of reference)
        → source-country EPC class  (via COUNTRY_CONSUMPTION_THRESHOLDS)
        → Italy old-scale EPC class (via COUNTRY_EPC_TO_ITALY)
        → Greek EPC class           (via ENERGY_CLASS_MAP_ITALY_TO_GREECE)
        → model input

Main Functions:
    - predict_arv: Predicts property value based on characteristics and energy consumption
    - _load_model: Loads the trained LightGBM model (called once at startup)
    - _map_property_type: Maps English labels to Greek labels used by model
    - _build_input_dataframe: Constructs model input features
    - resolve_epc_from_consumption: Full EPC resolution chain

Dependencies:
    - joblib: For loading the trained model
    - pandas: For input data structuring
    - lgb_model_greece.pkl: Trained LightGBM price prediction model for Greece
"""

import joblib
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Optional

from math import inf

from ..models.arv import (
    ARVRequest,
    ARVResponse,
    ARVValueSnapshot,
    ARVUplift,
    PropertyType,
)


# ============================================================================
# Module-level model singleton
# ============================================================================

_MODEL = None
_MODEL_PATH = Path(__file__).parent.parent / "data" / "lgb_model_greece.pkl"


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
                "Please ensure lgb_model_greece.pkl is in the data/ directory."
            )
        
        try:
            _MODEL = joblib.load(_MODEL_PATH)
        except Exception as e:
            raise RuntimeError(f"Failed to load model from {_MODEL_PATH}: {e}")
    
    return _MODEL


# ============================================================================
# EPC Mapping Tables
# ============================================================================

# Italy old-scale is the normalisation reference between all national scales
# and the Greek EPC classes used by the trained model.

ENERGY_CLASS_MAP_ITALY_TO_GREECE: dict[str, str] = {
    "A+": "Α+",
    "A":  "Α",
    "B":  "Β",
    "C":  "Γ",
    "D":  "Δ",
    "E":  "Ε",
    "F":  "Ζ",
    "G":  "Η",
}

# Maps each national EPC letter to the corresponding Italy old-scale letter.
COUNTRY_EPC_TO_ITALY: dict[str, dict[str, str]] = {
    "Greece": {
        "Α+": "A+", "Α": "A", "Β": "B", "Β+": "B",
        "Γ": "C", "Δ": "D", "Ε": "E", "Ζ": "F", "Η": "G",
    },
    "Italy": {
        "A+": "A+", "A": "A", "B": "B", "C": "C",
        "D": "D", "E": "E", "F": "F", "G": "G",
    },
    "Croatia": {
        "A+": "A+", "A": "A", "B": "B", "C": "E",
        "D": "F", "E": "G", "F": "G", "G": "G",
    },
    "Spain": {
        "A": "A+", "B": "C", "C": "D", "D": "F",
        "E": "F", "F": "G", "G": "G",
    },
    "Luxembourg Flats": {
        "A+": "A+", "A": "A", "B": "C", "C": "E", "D": "E",
        "E": "F", "F": "G", "G": "G", "H": "G", "I": "G",
    },
    "Luxembourg Houses": {
        "A+": "A+", "A": "B", "B": "D", "C": "F", "D": "G",
        "E": "G", "F": "G", "G": "G", "H": "G", "I": "G",
    },
    "Belgium Brussels": {
        "A": "A", "B": "D", "C": "F", "D": "G",
        "E": "G", "F": "G", "G": "G",
    },
    "Belgium Wallonia": {
        "A+": "A", "A": "D", "B": "F", "C": "G",
        "D": "G", "E": "G", "F": "G", "G": "G",
    },
    "Belgium Flanders": {
        "A+": "A+", "A": "C", "B": "G", "C": "G",
        "D": "G", "E": "G", "F": "G",
    },
    "Denmark": {
        "A": "A", "B": "D", "C": "F", "D": "G", "E": "G", "F": "G",
    },
    "Germany": {
        "A+": "A+", "A": "B", "B": "D", "C": "E", "D": "F",
        "E": "G", "F": "G", "G": "G", "H": "G",
    },
    "France": {
        "A": "B", "B": "E", "C": "G", "D": "G",
        "E": "G", "F": "G", "G": "G",
    },
    "Finland": {
        "A": "B", "B": "E", "C": "F", "D": "G",
        "E": "G", "F": "G", "G": "G",
    },
    "Austria": {
        "A++": "B", "A+": "D", "A": "E", "B": "F",
        "C": "G", "D": "G", "E": "G", "F": "G", "G": "G",
    },
    "Norway": {
        "A": "B", "B": "E", "C": "F", "D": "F",
        "E": "G", "F": "G", "G": "G",
    },
    "Bulgaria": {
        "A": "C", "B": "G", "C": "G", "D": "G",
        "E": "G", "F": "G", "G": "G",
    },
    "Netherlands": {
        "A++++": "A+", "A+++": "A", "A++": "D", "A+": "E",
        "A": "G", "B": "G", "C": "G", "D": "G", "E": "G",
        "F": "G", "G": "G",
    },
    "Romania": {
        "A": "C", "B": "G", "C": "G", "D": "G",
    },
    "Slovakia": {
        "A": "D", "B": "G", "C": "G", "D": "G",
    },
    "Portugal": {
        "A+": "A+", "A": "B", "B": "D", "B-": "E",
        "C": "F", "D": "G", "E": "G", "F": "G",
    },
    "Czech Republic": {
        "A": "A", "B": "D", "C": "E", "D": "F",
        "E": "G", "F": "G", "G": "G",
    },
}

# Energy-consumption thresholds per country.
# Format: (source_epc_class, upper_bound_inclusive).
# For Portugal and Czech Republic, bounds are % of reference, not kWh/m²/year.
COUNTRY_CONSUMPTION_THRESHOLDS: dict[str, list[tuple[str, float]]] = {
    "Croatia":           [("A+", 15.0), ("A", 25.0), ("B", 50.0), ("C", 100.0), ("D", 150.0), ("E", 200.0), ("F", 250.0), ("G", inf)],
    "Italy":             [("A+", 19.2), ("A", 29.5), ("B", 42.7), ("C", 59.0),  ("D", 72.2),  ("E", 95.7),  ("F", 132.5), ("G", inf)],
    "Spain":             [("A", 34.1), ("B", 55.5), ("C", 85.4), ("D", 111.0), ("E", 136.6), ("F", 170.7), ("G", inf)],
    "Luxembourg Flats":  [("A+", 16.0), ("A", 41.0), ("B", 71.0), ("C", 84.0), ("D", 98.0), ("E", 154.0), ("F", 225.0), ("G", 280.0), ("H", 355.0), ("I", inf)],
    "Luxembourg Houses": [("A+", 22.0), ("A", 41.0), ("B", 90.0), ("C", 123.0), ("D", 142.0), ("E", 208.0), ("F", 295.0), ("G", 395.0), ("H", 530.0), ("I", inf)],
    "Belgium Brussels":  [("A", 45.0), ("B", 95.0), ("C", 150.0), ("D", 210.0), ("E", 275.0), ("F", 345.0), ("G", inf)],
    "Denmark":           [("A", 50.0), ("B", 90.0), ("C", 150.0), ("D", 230.0), ("E", 330.0), ("F", inf)],
    "Germany":           [("A+", 30.0), ("A", 50.0), ("B", 75.0), ("C", 100.0), ("D", 130.0), ("E", 160.0), ("F", 200.0), ("G", 250.0), ("H", inf)],
    "France":            [("A", 70.0), ("B", 110.0), ("C", 180.0), ("D", 250.0), ("E", 330.0), ("F", 420.0), ("G", inf)],
    "Finland":           [("A", 75.0), ("B", 100.0), ("C", 130.0), ("D", 160.0), ("E", 190.0), ("F", 240.0), ("G", inf)],
    "Austria":           [("A++", 60.0), ("A+", 70.0), ("A", 80.0), ("B", 160.0), ("C", 220.0), ("D", 280.0), ("E", 340.0), ("F", 400.0), ("G", inf)],
    "Belgium Wallonia":  [("A+", 45.0), ("A", 85.0), ("B", 170.0), ("C", 255.0), ("D", 340.0), ("E", 425.0), ("F", 510.0), ("G", inf)],
    "Norway":            [("A", 85.0), ("B", 95.0), ("C", 110.0), ("D", 135.0), ("E", 160.0), ("F", 200.0), ("G", inf)],
    "Bulgaria":          [("A", 95.0), ("B", 190.0), ("C", 240.0), ("D", 290.0), ("E", 363.0), ("F", 435.0), ("G", inf)],
    "Belgium Flanders":  [("A+", 0.0), ("A", 100.0), ("B", 200.0), ("C", 300.0), ("D", 400.0), ("E", 500.0), ("F", inf)],
    "Netherlands":       [("A++++", 0.0), ("A+++", 50.0), ("A++", 75.0), ("A+", 105.0), ("A", 160.0), ("B", 190.0), ("C", 250.0), ("D", 290.0), ("E", 335.0), ("F", 380.0), ("G", inf)],
    "Romania":           [("A", 115.0), ("B", 228.0), ("C", 344.0), ("D", 459.0)],
    "Slovakia":          [("A", 140.0), ("B", 280.0), ("C", 420.0), ("D", 558.0)],
    "Portugal":          [("A+", 25.0), ("A", 50.0), ("B", 75.0), ("B-", 100.0), ("C", 150.0), ("D", 200.0), ("E", 250.0), ("F", inf)],
    "Czech Republic":    [("A", 50.0), ("B", 75.0), ("C", 100.0), ("D", 150.0), ("E", 200.0), ("F", 250.0), ("G", inf)],
}
# Greece has no official consumption thresholds; borrow Italy's as approximation.
COUNTRY_CONSUMPTION_THRESHOLDS["Greece"] = COUNTRY_CONSUMPTION_THRESHOLDS["Italy"]

# Human-readable energy unit note per country (for metadata)
COUNTRY_SCALE_NOTES: dict[str, str] = {
    "Portugal": "% of reference, not kWh/m²/year",
    "Czech Republic": "% of reference, not kWh/m²/year",
}

# Lowercase aliases accepted in the `target_country` request field
COUNTRY_ALIASES: dict[str, str] = {
    "greece": "Greece",
    "hellas": "Greece",
    "italy": "Italy",
    "croatia": "Croatia",
    "spain": "Spain",
    "luxembourg apartments": "Luxembourg Flats",
    "luxembourg flats": "Luxembourg Flats",
    "luxembourg houses": "Luxembourg Houses",
    "belgium brussels": "Belgium Brussels",
    "brussels": "Belgium Brussels",
    "belgium wallonia": "Belgium Wallonia",
    "wallonia": "Belgium Wallonia",
    "belgium flanders": "Belgium Flanders",
    "flanders": "Belgium Flanders",
    "denmark": "Denmark",
    "germany": "Germany",
    "france": "France",
    "finland": "Finland",
    "austria": "Austria",
    "norway": "Norway",
    "bulgaria": "Bulgaria",
    "netherlands": "Netherlands",
    "romania": "Romania",
    "slovakia": "Slovakia",
    "portugal": "Portugal",
    "czech republic": "Czech Republic",
    "czechia": "Czech Republic",
}


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
# EPC Resolution Functions
# ============================================================================

def normalize_target_country(target_country: str) -> str:
    """
    Return the canonical country name from a user-supplied string.
    
    Accepts full names and common aliases (case-insensitive).
    
    Raises:
        ValueError: If the country is not recognised.
    """
    key = target_country.strip().lower()
    canonical = COUNTRY_ALIASES.get(key)
    if canonical is None:
        allowed = ", ".join(sorted(COUNTRY_CONSUMPTION_THRESHOLDS.keys()))
        raise ValueError(
            f"Unknown target_country: {target_country!r}. "
            f"Supported countries: {allowed}"
        )
    return canonical


def energy_consumption_to_source_epc(canonical_country: str, energy_consumption: float) -> str:
    """
    Look up the national EPC class from an energy-consumption value.
    
    Args:
        canonical_country: Normalised country name (from normalize_target_country)
        energy_consumption: kWh/m²/year (or % of reference for PT/CZ)
    
    Returns:
        National EPC class letter (e.g. "A+", "B", "G")
    
    Raises:
        ValueError: If consumption is negative or country has no thresholds
    """
    thresholds = COUNTRY_CONSUMPTION_THRESHOLDS[canonical_country]
    for epc_class, upper_bound in thresholds:
        if energy_consumption <= upper_bound:
            return epc_class
    # Fallback: return the last (worst) class
    return thresholds[-1][0]


def map_source_epc_to_italy(canonical_country: str, source_epc: str) -> str:
    """
    Map a national EPC class to the Italy old-scale EPC class.
    
    Args:
        canonical_country: Normalised country name
        source_epc: National EPC class (e.g. "B", "A++")
    
    Returns:
        Italy old-scale EPC class (e.g. "A+", "C", "G")
    
    Raises:
        ValueError: If source_epc is not in the country mapping
    """
    class_map = COUNTRY_EPC_TO_ITALY[canonical_country]
    try:
        return class_map[source_epc]
    except KeyError:
        allowed = ", ".join(class_map.keys())
        raise ValueError(
            f"Cannot map EPC class {source_epc!r} for {canonical_country!r}. "
            f"Allowed classes: {allowed}"
        )


def map_italy_epc_to_greek(italy_epc: str) -> str:
    """
    Map an Italy old-scale EPC class to the Greek EPC class used by the model.
    
    Args:
        italy_epc: Italy old-scale EPC class ("A+" through "G")
    
    Returns:
        Greek EPC class using Unicode Greek letters (e.g. "Α+", "Β", "Η")
    
    Raises:
        ValueError: If italy_epc is not in the mapping table
    """
    try:
        return ENERGY_CLASS_MAP_ITALY_TO_GREECE[italy_epc]
    except KeyError:
        allowed = ", ".join(ENERGY_CLASS_MAP_ITALY_TO_GREECE.keys())
        raise ValueError(
            f"Cannot map Italy EPC class {italy_epc!r} to Greek EPC. "
            f"Allowed values: {allowed}"
        )


def resolve_epc_from_consumption(
    target_country: str,
    energy_consumption: float,
) -> dict[str, str]:
    """
    Full EPC resolution chain:
        energy_consumption -> source EPC -> Italy EPC -> Greek EPC
    
    Args:
        target_country: User-supplied country name (aliases accepted)
        energy_consumption: Consumption value in kWh/m²/year (or % of reference for PT/CZ)
    
    Returns:
        Dict with keys: target_country, source_epc_class, italy_epc_class, greek_epc_class
    
    Raises:
        ValueError: If the country is unknown or a mapping step fails
    """
    canonical = normalize_target_country(target_country)
    source_epc = energy_consumption_to_source_epc(canonical, energy_consumption)
    italy_epc = map_source_epc_to_italy(canonical, source_epc)
    greek_epc = map_italy_epc_to_greek(italy_epc)
    return {
        "target_country": canonical,
        "source_epc_class": source_epc,
        "italy_epc_class": italy_epc,
        "greek_epc_class": greek_epc,
    }


# ============================================================================
# Input Data Preparation
# ============================================================================

def _build_input_dataframe(
    request: ARVRequest,
    greek_epc_class: str,
) -> pd.DataFrame:
    """
    Build a single-row DataFrame with features expected by the trained model.
    
    The model expects these columns:
    - Numeric: floor_area, building_age, floor_number, lat, lng, number_of_floors
    - Categorical: energy_class (Greek EPC), type (property type in Greek)
    - Boolean: renovated_last_5_years
    
    Args:
        request: ARVRequest with property characteristics
        greek_epc_class: Resolved Greek EPC class from the EPC resolution chain
        
    Returns:
        Single-row DataFrame ready for model.predict()
    """
    current_year = datetime.now().year
    building_age = current_year - request.construction_year
    property_type_greek = _map_property_type(request.property_type)
    
    data = {
        "floor_area":             [request.floor_area],
        "building_age":           [building_age],
        "floor_number":           [request.floor_number],
        "lat":                    [request.lat],
        "lng":                    [request.lng],
        "number_of_floors":       [request.number_of_floors],
        "energy_class":           [greek_epc_class],
        "type":                   [property_type_greek],
        "renovated_last_5_years": [request.renovated_last_5_years],
    }
    
    return pd.DataFrame(data)


# ============================================================================
# Main Service Function
# ============================================================================

async def predict_arv(request: ARVRequest) -> ARVResponse:
    """
    Predict After Renovation Value (ARV) for a property.

    Always computes the post-renovation value (energy_consumption_after).
    When energy_consumption_before is also provided, additionally computes
    the pre-renovation value and the monetary/percentage uplift.

    EPC resolution chain per consumption value:
        energy_consumption -> source EPC -> Italy EPC -> Greek EPC -> model

    Args:
        request: ARVRequest containing property characteristics

    Returns:
        ARVResponse with after (always), before + uplift (when before consumption given)

    Raises:
        FileNotFoundError: If model file is missing
        RuntimeError: If model loading or prediction fails
        ValueError: If target_country is unknown or EPC mapping fails
    """

    # ─────────────────────────────────────────────────────────────
    # Step 1: Load Model
    # ─────────────────────────────────────────────────────────────

    try:
        model = _load_model()
    except Exception as e:
        raise RuntimeError(f"Model loading failed: {e}")

    # ─────────────────────────────────────────────────────────────
    # Step 2: Helper — run one prediction for a given consumption value
    # ─────────────────────────────────────────────────────────────

    def _predict_snapshot(consumption: float) -> ARVValueSnapshot:
        epc = resolve_epc_from_consumption(request.target_country, consumption)
        df = _build_input_dataframe(request, epc["greek_epc_class"])
        price_per_sqm = float(model.predict(df)[0])
        return ARVValueSnapshot(
            price_per_sqm=price_per_sqm,
            total_price=price_per_sqm * request.floor_area,
            greek_epc_class=epc["greek_epc_class"],
            epc_resolution=epc,
        )

    # ─────────────────────────────────────────────────────────────
    # Step 3: Compute after (always) and before (if provided)
    # ─────────────────────────────────────────────────────────────

    try:
        snapshot_after = _predict_snapshot(request.energy_consumption_after)
        snapshot_before = (
            _predict_snapshot(request.energy_consumption_before)
            if request.energy_consumption_before is not None
            else None
        )
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Prediction failed: {e}")

    # ─────────────────────────────────────────────────────────────
    # Step 4: Compute uplift
    # ─────────────────────────────────────────────────────────────

    uplift = None
    if snapshot_before is not None:
        price_increase = snapshot_after.total_price - snapshot_before.total_price
        price_increase_pct = (price_increase / snapshot_before.total_price) * 100
        uplift = ARVUplift(
            price_increase=round(price_increase, 2),
            price_increase_pct=round(price_increase_pct, 2),
        )

    # ─────────────────────────────────────────────────────────────
    # Step 5: Build metadata
    # ─────────────────────────────────────────────────────────────

    current_year = datetime.now().year
    building_age = current_year - request.construction_year
    canonical_country = normalize_target_country(request.target_country)

    metadata = {
        "model_file": "lgb_model_greece.pkl",
        "prediction_timestamp": datetime.now().isoformat(),
        "building_age": building_age,
        "property_type_mapped": _map_property_type(request.property_type),
        "energy_consumption_unit": COUNTRY_SCALE_NOTES.get(canonical_country, "kWh/m²/year"),
        "input_features": {
            "lat":                         request.lat,
            "lng":                         request.lng,
            "floor_area":                  request.floor_area,
            "building_age":                building_age,
            "floor_number":                request.floor_number,
            "number_of_floors":            request.number_of_floors,
            "energy_consumption_after":    request.energy_consumption_after,
            "energy_consumption_before":   request.energy_consumption_before,
            "renovated_last_5_years":      request.renovated_last_5_years,
        },
    }

    return ARVResponse(
        after=snapshot_after,
        before=snapshot_before,
        uplift=uplift,
        floor_area=request.floor_area,
        metadata=metadata,
    )
