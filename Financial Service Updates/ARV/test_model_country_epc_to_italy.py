"""
test_model_greece_mapped.py

Purpose
-------
Small helper script to:
  1. Load the trained Greece price prediction model from `lgb_model_greece.pkl`
  2. Accept a target country from the available country mappings
  3. Map the input EPC / energy class to Italy old-scale EPC
  4. Convert the Italy old-scale EPC to the Greek EPC class
  5. Run a sample prediction and print the results

Current EPC mapping
-------------------
All available country/region EPC scales from the Excel are mapped first to the
Italy old-scale EPC labels. That result is then converted to the Greek EPC
labels expected by the Greece price model. UK, Ireland, and the newer/observed
Italy scale are excluded. Greece is not present in the Excel, so it is mapped to 
Italy using the Greek -> Italy dictionary.

Usage
-----
- Install dependencies, for example:
    pip install joblib pandas lightgbm

- Run the default example:
    python test_model_greece_mapped.py

- Run with explicit inputs:
    python test_model_greece_mapped.py \
        --target-country Greece \
        --lat 37.981 \
        --lng 23.728 \
        --floor-area 85 \
        --construction-year 1985 \
        --floor-number 2 \
        --energy-class Η \
        --property-type-ui Villa \
        --renovated-last-5-years false \
        --number-of-floors 5
"""

from __future__ import annotations

import argparse
from datetime import datetime
import sys
from typing import Any

from pathlib import Path

import joblib
import numpy as np
import pandas as pd

MODEL_PATH = Path(__file__).resolve().parent / "lgb_model_greece.pkl"

# -------------------------------------------------------------------------
# Country / EPC mappings
# -------------------------------------------------------------------------
# Mapping principle:
#   Each source-country EPC class is converted to the closest Italy old-scale
#   class using the EPC threshold bands in the Excel. Where a source class spans
#   multiple Italy bands, the midpoint of the source class range is used.

MODEL_EPC_CLASSES = ("A+", "A", "B", "C", "D", "E", "F", "G")

ENERGY_CLASS_MAP_GREECE_TO_ITALY = {
    "Α+": "A+",
    "Α": "A",
    "Β": "B",
    "Β+": "B",
    "Γ": "C",
    "Δ": "D",
    "Ε": "E",
    "Ζ": "F",
    "Η": "G",
}

ENERGY_CLASS_MAP_ITALY_TO_GREECE = {
    "A+": "Α+",
    "A": "Α",
    "B": "Β",
    "C": "Γ",
    "D": "Δ",
    "E": "Ε",
    "F": "Ζ",
    "G": "Η",
}

ENERGY_CLASS_MAPS_TO_ITALY = {
    "Greece": ENERGY_CLASS_MAP_GREECE_TO_ITALY,
    "Italy": {
        "A+": "A+",
        "A": "A",
        "B": "B",
        "C": "C",
        "D": "D",
        "E": "E",
        "F": "F",
        "G": "G",
    },
    "Croatia": {
        "A+": "A+",
        "A": "A",
        "B": "B",
        "C": "E",
        "D": "F",
        "E": "G",
        "F": "G",
        "G": "G",
    },
    "Spain": {
        "A": "A+",
        "B": "C",
        "C": "D",
        "D": "F",
        "E": "F",
        "F": "G",
        "G": "G",
    },
    "Luxembourg Flats": {
        "A+": "A+",
        "A": "A",
        "B": "C",
        "C": "E",
        "D": "E",
        "E": "F",
        "F": "G",
        "G": "G",
        "H": "G",
        "I": "G",
    },
    "Luxembourg Houses": {
        "A+": "A+",
        "A": "B",
        "B": "D",
        "C": "F",
        "D": "G",
        "E": "G",
        "F": "G",
        "G": "G",
        "H": "G",
        "I": "G",
    },
    "Belgium Brussels": {
        "A": "A",
        "B": "D",
        "C": "F",
        "D": "G",
        "E": "G",
        "F": "G",
        "G": "G",
    },
    "Belgium Wallonia": {
        "A+": "A",
        "A": "D",
        "B": "F",
        "C": "G",
        "D": "G",
        "E": "G",
        "F": "G",
        "G": "G",
    },
    "Belgium Flanders": {
        "A+": "A+",
        "A": "C",
        "B": "G",
        "C": "G",
        "D": "G",
        "E": "G",
        "F": "G",
    },
    "Denmark": {
        "A": "A",
        "B": "D",
        "C": "F",
        "D": "G",
        "E": "G",
        "F": "G",
    },
    "Germany": {
        "A+": "A+",
        "A": "B",
        "B": "D",
        "C": "E",
        "D": "F",
        "E": "G",
        "F": "G",
        "G": "G",
        "H": "G",
    },
    "France": {
        "A": "B",
        "B": "E",
        "C": "G",
        "D": "G",
        "E": "G",
        "F": "G",
        "G": "G",
    },
    "Finland": {
        "A": "B",
        "B": "E",
        "C": "F",
        "D": "G",
        "E": "G",
        "F": "G",
        "G": "G",
    },
    "Austria": {
        "A++": "B",
        "A+": "D",
        "A": "E",
        "B": "F",
        "C": "G",
        "D": "G",
        "E": "G",
        "F": "G",
        "G": "G",
    },
    "Norway": {
        "A": "B",
        "B": "E",
        "C": "F",
        "D": "F",
        "E": "G",
        "F": "G",
        "G": "G",
    },
    "Bulgaria": {
        "A": "C",
        "B": "G",
        "C": "G",
        "D": "G",
        "E": "G",
        "F": "G",
        "G": "G",
    },
    "Netherlands": {
        "A++++": "A+",
        "A+++": "A",
        "A++": "D",
        "A+": "E",
        "A": "G",
        "B": "G",
        "C": "G",
        "D": "G",
        "E": "G",
        "F": "G",
        "G": "G",
    },
    "Romania": {
        "A": "C",
        "B": "G",
        "C": "G",
        "D": "G",
    },
    "Slovakia": {
        "A": "D",
        "B": "G",
        "C": "G",
        "D": "G",
    },
    "Portugal": {
        "A+": "A+",
        "A": "B",
        "B": "D",
        "B-": "E",
        "C": "F",
        "D": "G",
        "E": "G",
        "F": "G",
    },
    "Czech Republic": {
        "A": "A",
        "B": "D",
        "C": "E",
        "D": "F",
        "E": "G",
        "F": "G",
        "G": "G",
    },
}

# shown in AVAILABLE_TARGET_COUNTRIES.
COUNTRY_ALIASES = {
    "greece": "Greece",
    "hellas": "Greece",
    "italy": "Italy",
    "croatia": "Croatia",
    "spain": "Spain",
    "luxembourg apartments": "Luxembourg Flats",
    "luxembourg houses": "Luxembourg Houses",
    "brussels": "Belgium Brussels",
    "wallonia": "Belgium Wallonia",
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
}

COUNTRY_ENERGY_CLASS_MAPS = ENERGY_CLASS_MAPS_TO_ITALY
AVAILABLE_TARGET_COUNTRIES = tuple(COUNTRY_ENERGY_CLASS_MAPS.keys())

# -------------------------------------------------------------------------
# Allowed values for `property_type_ui`.
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


def parse_bool(value: str | bool) -> bool:
    """Parse a command-line boolean value."""
    if isinstance(value, bool):
        return value

    normalized = value.strip().lower()
    if normalized in {"true", "t", "yes", "y", "1"}:
        return True
    if normalized in {"false", "f", "no", "n", "0"}:
        return False

    raise argparse.ArgumentTypeError(
        "Expected a boolean value: true/false, yes/no, or 1/0."
    )


def configure_stdio() -> None:
    """
    Prefer UTF-8 output so Greek labels print correctly on Windows shells.
    """
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8")


def load_model(model_path: str | Path) -> Any:
    """
    Load the saved model with clearer guidance for missing/invalid paths.
    """
    try:
        return joblib.load(model_path)
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"Model file not found: {model_path!s}. "
            "Expected the Greece model pickle in the ARV_mapping folder."
        ) from exc
    except ModuleNotFoundError as exc:
        if exc.name == "lightgbm":
            raise ModuleNotFoundError(
                "The saved model requires `lightgbm` to be installed before it "
                "can be loaded. Install it with: pip install lightgbm"
            ) from exc
        raise


def parse_floor_number(value: str) -> float:
    """Parse floor number and allow NaN for unknown floor."""
    if value.strip().lower() in {"nan", "none", "null", ""}:
        return float("nan")
    return float(value)


def map_property_type(ui_label: str) -> str:
    """
    Map a property type label, usually from the UI, to the Greek label
    that the model was trained on.
    """
    try:
        return PROPERTY_TYPE_MAP[ui_label]
    except KeyError as exc:
        allowed = ", ".join(sorted(PROPERTY_TYPE_MAP.keys()))
        raise ValueError(
            f"Unknown property_type_ui option: {ui_label!r}. "
            f"Allowed values are: {allowed}"
        ) from exc


def normalize_target_country(target_country: str) -> str:
    """Return the canonical country/region name used by the EPC mappings."""
    key = target_country.strip().lower()
    if key in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[key]

    allowed = ", ".join(AVAILABLE_TARGET_COUNTRIES)
    raise ValueError(
        f"Unknown target_country: {target_country!r}. "
        f"Available target countries are: {allowed}"
    )


def map_energy_class(target_country: str, energy_class: str) -> str:
    """
    Map the input EPC / energy class for the selected target country to the
    Italy old-scale EPC label expected by the model.

    Raises:
        ValueError: if the country or energy class is not supported.
    """
    canonical_country = normalize_target_country(target_country)
    class_map = COUNTRY_ENERGY_CLASS_MAPS[canonical_country]
    normalized_energy_class = energy_class.strip().upper()

    try:
        return class_map[normalized_energy_class]
    except KeyError as exc:
        allowed_classes = ", ".join(class_map.keys())
        raise ValueError(
            f"Unknown energy_class {energy_class!r} for target_country "
            f"{canonical_country!r}. Allowed EPC classes are: {allowed_classes}"
        ) from exc


def map_italy_epc_to_greek(italy_epc_class: str) -> str:
    """Map Italy old-scale EPC to the Greek EPC class used by the Greece model."""
    try:
        return ENERGY_CLASS_MAP_ITALY_TO_GREECE[italy_epc_class]
    except KeyError as exc:
        allowed = ", ".join(ENERGY_CLASS_MAP_ITALY_TO_GREECE.keys())
        raise ValueError(
            f"Cannot map Italy EPC class {italy_epc_class!r} to Greek EPC. "
            f"Allowed Italy classes are: {allowed}"
        ) from exc


def build_input_row(
    *,
    target_country: str,
    lat: float,
    lng: float,
    floor_area: float,
    construction_year: int,
    floor_number: float,
    energy_class: str,
    property_type_ui: str,
    renovated_last_5_years: bool,
    number_of_floors: int,
) -> tuple[pd.DataFrame, dict[str, str]]:
    """
    Build a single-row DataFrame with the same columns the model expects.

    The user-facing `energy_class` is country-specific. It is mapped first to
    Italy old-scale EPC, then to the Greek EPC label expected by the model.
    """
    current_year = datetime.now().year
    building_age = current_year - construction_year

    property_type_greek = map_property_type(property_type_ui)
    canonical_target_country = normalize_target_country(target_country)
    italy_energy_class = map_energy_class(target_country, energy_class)
    model_energy_class = map_italy_epc_to_greek(italy_energy_class)

    data: dict[str, list[Any]] = {
        # numeric features
        "floor_area": [floor_area],
        "building_age": [building_age],
        "floor_number": [floor_number],
        "lat": [lat],
        "lng": [lng],

        # categorical / boolean features
        "energy_class": [model_energy_class],
        "type": [property_type_greek],
        "renovated_last_5_years": [renovated_last_5_years],
        "number_of_floors": [number_of_floors],
    }

    return pd.DataFrame(data), {
        "target_country": canonical_target_country,
        "input_energy_class": energy_class,
        "italy_epc_class": italy_energy_class,
        "greek_epc_class": model_energy_class,
        "model_epc_class": model_energy_class,
    }


def predict_price_per_sqm(model: Any, input_row: pd.DataFrame) -> float:
    """Run the model and return the predicted price per square meter."""
    return float(model.predict(input_row)[0])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Predict property price using country-specific EPC mapping."
    )
    parser.add_argument(
        "--target-country",
        default="Greece",
        help="Country whose EPC scale the input energy_class uses. Aliases such as 'czechia' and 'brussels' are accepted.",
    )
    parser.add_argument("--lat", type=float, default=37.981)
    parser.add_argument("--lng", type=float, default=23.728)
    parser.add_argument("--floor-area", type=float, default=85.0)
    parser.add_argument("--construction-year", type=int, default=1985)
    parser.add_argument("--floor-number", type=parse_floor_number, default=np.nan)
    parser.add_argument("--energy-class", default="Η")
    parser.add_argument(
        "--property-type-ui",
        default="Villa",
        choices=tuple(PROPERTY_TYPE_MAP.keys()),
    )
    parser.add_argument(
        "--renovated-last-5-years",
        type=parse_bool,
        default=False,
    )
    parser.add_argument("--number-of-floors", type=int, default=5)
    return parser


def main() -> None:
    configure_stdio()
    parser = build_parser()
    args = parser.parse_args()

    print("=== Available target countries ===")
    print("  " + ", ".join(AVAILABLE_TARGET_COUNTRIES))
    print()

    print("=== Model input description ===")
    print("Required fields and types:")
    print("  target_country (str)         - one of:", ", ".join(AVAILABLE_TARGET_COUNTRIES))
    print("  lat (float)                  - latitude")
    print("  lng (float)                  - longitude")
    print("  floor_area (float)           - m²")
    print("  construction_year (int)      - e.g. 1985")
    print("  floor_number (float)         - use nan if unknown")
    print("  energy_class (str)           - e.g. for Greece: 'Η', 'Ζ', 'Ε', 'Δ', 'Γ', 'Β', 'Β+', 'Α', 'Α+'")
    print("  property_type_ui (str)       - one of:", ", ".join(PROPERTY_TYPE_MAP.keys()))
    print("  renovated_last_5_years (bool)")
    print("  number_of_floors (int)")
    print()

    print(f"Loading model from: {MODEL_PATH}")
    model = load_model(MODEL_PATH)
    print("Model loaded successfully.\n")

    input_values = {
        "target_country": args.target_country,
        "lat": args.lat,
        "lng": args.lng,
        "floor_area": args.floor_area,
        "construction_year": args.construction_year,
        "floor_number": args.floor_number,
        "energy_class": args.energy_class,
        "property_type_ui": args.property_type_ui,
        "renovated_last_5_years": args.renovated_last_5_years,
        "number_of_floors": args.number_of_floors,
    }

    print("=== Raw input ===")
    for key, value in input_values.items():
        print(f"  {key}: {value}")
    print()

    row, epc_info = build_input_row(**input_values)

    print("=== Mapped model input ===")
    print(f"  target_country: {epc_info['target_country']}")
    print(f"  input_energy_class: {epc_info['input_energy_class']}")
    print(f"  italy_old_scale_epc_class: {epc_info['italy_epc_class']}")
    print(f"  greek_epc_class: {epc_info['greek_epc_class']}")
    print(f"  model_energy_class: {epc_info['model_epc_class']}")
    print(row.to_string(index=False))
    print()

    y_pred = predict_price_per_sqm(model, row)
    total_price = y_pred * row["floor_area"].iloc[0]

    print("=== Prediction result ===")
    print(f"  price_per_sqm: {y_pred:.2f} €")
    print(f"  total_price:   {total_price:.2f} €")


if __name__ == "__main__":
    main()
