"""
test_model.py

Purpose
-------
Small helper script to:
  1. Load the trained price prediction model from `lgb_model.pkl`
  2. Show what inputs the model expects
  3. Run a sample prediction and print the results

Usage
-----
- The model file should be in the same folder:
    lgb_model.pkl

- Install dependencies (example):
    pip install joblib pandas lightgbm

- Run:
    python test_model.py
"""

import joblib
import pandas as pd
import numpy as np
from datetime import datetime

MODEL_PATH = "lgb_model.pkl"

# -------------------------------------------------------------------------
#
# Allowed values for `property_type_ui`:
#
# - Loft
# - Studio / Γκαρσονιέρα
# - Βίλα
# - Διαμέρισμα
# - Κτίριο
# - Λοιπές κατηγορίες
# - Μεζονέτα
# - Μονοκατοικία
# - Συγκρότημα διαμερισμάτων
#
# These are mapped to the Greek labels that the model was trained on.
# -------------------------------------------------------------------------
PROPERTY_TYPE_MAP = {
    "Loft": "Loft",
    "Studio / Bedsit": "Studio / Γκαρσονιέρα",
    "Villa": "Βίλα",
    "Apartment": "Διαμέρισμα",
    "Building": "Κτίριο",
    "Other": "Λοιπές κατηγορίες",
    "Maisonette": "Μεζονέτα",
    "Detached House": "Μονοκατοικία",
    "Apartment Complex": "Συγκρότημα διαμερισμάτων",
}


def map_property_type(ui_label: str) -> str:
    """
    Map a property type label (English label) to the Greek label
    that the model was trained on.

    Raises:
        ValueError: if ui_label is not in PROPERTY_TYPE_MAP.
    """
    try:
        return PROPERTY_TYPE_MAP[ui_label]
    except KeyError:
        allowed = ", ".join(sorted(PROPERTY_TYPE_MAP.keys()))
        raise ValueError(
            f"Unknown property_type option: {ui_label!r}. "
            f"Allowed values are: {allowed}"
        )


def build_input_row(
    *,
    lat: float,
    lng: float,
    floor_area: float,
    construction_year: int,
    floor_number: int,
    energy_class: str,
    property_type_ui: str,
    renovated_last_5_years: bool,
    number_of_floors: int,
) -> pd.DataFrame:
    """
    Build a single-row DataFrame with the same columns the model was trained on.

    Parameters
    ----------
    lat : float
        Latitude of the property (e.g. 37.981)
    lng : float
        Longitude of the property (e.g. 23.728)
    floor_area : float
        Floor area in square meters (m²)
    construction_year : int
        Year the building was constructed (e.g. 1985)
    floor_number : int
        Floor number where the property is located (e.g. 2)
    energy_class : str
        Energy efficiency class, e.g. "Γ", "Β+", "Α"
    property_type_ui : str
        One of the keys in PROPERTY_TYPE_MAP (English labels listed above)
    renovated_last_5_years : bool
        True if the property has been renovated in the last 5 years, else False
    number_of_floors : int
        Total number of floors in the building

    Returns
    -------
    pd.DataFrame
        A single-row DataFrame ready to be passed to model.predict()
    """

    current_year = datetime.now().year
    building_age = current_year - construction_year

    # Map the UI choice to the Greek categorical label
    property_type_greek = map_property_type(property_type_ui)

    data = {
        # numeric features
        "floor_area": [floor_area],
        "building_age": [building_age],
        "floor_number": [floor_number],
        "lat": [lat],
        "lng": [lng],

        # categorical / boolean features
        "energy_class": [energy_class], 
        "type": [property_type_greek],   # Greek label
        "renovated_last_5_years": [renovated_last_5_years],
        "number_of_floors": [number_of_floors],
    }

    return pd.DataFrame(data)


def main():
    # ---------------------------------------------------------------------
    # 1. Quick overview of the expected inputs
    # ---------------------------------------------------------------------
    print("=== Model input description ===")
    print("Required fields and types:")
    print("  lat (float)                  - latitude")
    print("  lng (float)                  - longitude")
    print("  floor_area (float)           - m²")
    print("  construction_year (int)      - e.g. 1985")
    print("  floor_number (int)")
    print("  energy_class (str)           - e.g. 'Γ', 'Β+', 'Α'")
    print("  property_type_ui (str)       - one of:", ", ".join(PROPERTY_TYPE_MAP.keys()))
    print("  renovated_last_5_years (bool)")
    print("  number_of_floors (int)")
    print()

    # For reference
    ENERGY_CLASS_ORDER = ["Η", "Ζ", "Ε", "Δ", "Γ", "Β", "Β+", "Α", "Α+"]

    # ---------------------------------------------------------------------
    # 2. Load trained pipeline 
    # ---------------------------------------------------------------------
    print(f"Loading model from: {MODEL_PATH}")
    model = joblib.load(MODEL_PATH)
    print("Model loaded successfully.\n")

    # ---------------------------------------------------------------------
    # 3. Example property 
    # ---------------------------------------------------------------------
    example_inputs = {
        "lat": 37.981,
        "lng": 23.728,
        "floor_area": 85.0,
        "construction_year": 1985,
        "floor_number": np.nan,
        "energy_class": "Η",
        "property_type_ui": "Villa",  
        "renovated_last_5_years": False,
        "number_of_floors": 5,
    }

    print("=== Example input ===")
    for k, v in example_inputs.items():
        print(f"  {k}: {v}")
    print()

    row = build_input_row(**example_inputs)

    # ---------------------------------------------------------------------
    # 4. Run prediction
    # ---------------------------------------------------------------------
    y_pred = model.predict(row)[0]  
    total_price = y_pred * row["floor_area"].iloc[0]

    print("=== Prediction result ===")
    print(f"  price_per_sqm: {y_pred:.2f} €")
    print(f"  total_price:   {total_price:.2f} €")



if __name__ == "__main__":
    main()
