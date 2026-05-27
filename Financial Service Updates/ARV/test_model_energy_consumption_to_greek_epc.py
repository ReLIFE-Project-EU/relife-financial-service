"""
test_model_energy_consumption_to_greek_epc.py

Purpose
-------
Small helper script to:
  1. Load the trained price prediction model from `lgb_model_greece.pkl`
  2. Accept a target country and an energy-consumption value
  3. Derive the local/source-country EPC class from the Excel thresholds
  4. Map that EPC class to Italy old-scale EPC
  5. Map the Italy old-scale EPC to the Greek EPC class
  6. Run the model using the mapped EPC class

Important notes
---------------
- UK, Ireland, and Italy new/observed scale are intentionally excluded.
- Greece is not in the Excel, so Greece is handled through the temporary
  Greece <-> Italy mapping you provided.
- For Portugal and Czech Republic, the Excel scale is "% of reference", not
  direct kWh/m²/year. The same numeric input argument is used, but the value
  should be interpreted as % of reference for those two countries.
- The final model input is always the Greek EPC label used by the Greece model.

Usage
-----
Install dependencies, for example:
    pip install joblib pandas lightgbm

Run the default example:
    python test_model_energy_consumption_to_greek_epc.py

Run with explicit inputs:
    python test_model_energy_consumption_to_greek_epc.py \
        --target-country Italy \
        --energy-consumption 85 \
        --lat 37.981 \
        --lng 23.728 \
        --floor-area 85 \
        --construction-year 1985 \
        --floor-number 2 \
        --property-type-ui Villa \
        --renovated-last-5-years false \
        --number-of-floors 5
"""

from __future__ import annotations

import argparse
from datetime import datetime
from math import inf
from pathlib import Path
import sys
from typing import Any

import joblib
import numpy as np
import pandas as pd

MODEL_PATH = Path(__file__).resolve().parent / "lgb_model_greece.pkl"

# -------------------------------------------------------------------------
# EPC class mappings
# -------------------------------------------------------------------------
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

COUNTRY_EPC_TO_ITALY = {
    "Greece": ENERGY_CLASS_MAP_GREECE_TO_ITALY,
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

# -------------------------------------------------------------------------
# Energy-consumption thresholds from the Excel
# -------------------------------------------------------------------------
# Format: country -> list of (source_epc_class, upper_bound).
# The first class whose upper_bound is >= energy_consumption is selected.
# For Portugal and Czech Republic, bounds are % of reference, not kWh/m²/year.
COUNTRY_CONSUMPTION_THRESHOLDS = {
    "Croatia": [("A+", 15.0), ("A", 25.0), ("B", 50.0), ("C", 100.0), ("D", 150.0), ("E", 200.0), ("F", 250.0), ("G", inf)],
    "Italy": [("A+", 19.2), ("A", 29.5), ("B", 42.7), ("C", 59.0), ("D", 72.2), ("E", 95.7), ("F", 132.5), ("G", inf)],
    "Spain": [("A", 34.1), ("B", 55.5), ("C", 85.4), ("D", 111.0), ("E", 136.6), ("F", 170.7), ("G", inf)],
    "Luxembourg Flats": [("A+", 16.0), ("A", 41.0), ("B", 71.0), ("C", 84.0), ("D", 98.0), ("E", 154.0), ("F", 225.0), ("G", 280.0), ("H", 355.0), ("I", inf)],
    "Luxembourg Houses": [("A+", 22.0), ("A", 41.0), ("B", 90.0), ("C", 123.0), ("D", 142.0), ("E", 208.0), ("F", 295.0), ("G", 395.0), ("H", 530.0), ("I", inf)],
    "Belgium Brussels": [("A", 45.0), ("B", 95.0), ("C", 150.0), ("D", 210.0), ("E", 275.0), ("F", 345.0), ("G", inf)],
    "Denmark": [("A", 50.0), ("B", 90.0), ("C", 150.0), ("D", 230.0), ("E", 330.0), ("F", inf)],
    "Germany": [("A+", 30.0), ("A", 50.0), ("B", 75.0), ("C", 100.0), ("D", 130.0), ("E", 160.0), ("F", 200.0), ("G", 250.0), ("H", inf)],
    "France": [("A", 70.0), ("B", 110.0), ("C", 180.0), ("D", 250.0), ("E", 330.0), ("F", 420.0), ("G", inf)],
    "Finland": [("A", 75.0), ("B", 100.0), ("C", 130.0), ("D", 160.0), ("E", 190.0), ("F", 240.0), ("G", inf)],
    "Austria": [("A++", 60.0), ("A+", 70.0), ("A", 80.0), ("B", 160.0), ("C", 220.0), ("D", 280.0), ("E", 340.0), ("F", 400.0), ("G", inf)],
    "Belgium Wallonia": [("A+", 45.0), ("A", 85.0), ("B", 170.0), ("C", 255.0), ("D", 340.0), ("E", 425.0), ("F", 510.0), ("G", inf)],
    "Norway": [("A", 85.0), ("B", 95.0), ("C", 110.0), ("D", 135.0), ("E", 160.0), ("F", 200.0), ("G", inf)],
    "Bulgaria": [("A", 95.0), ("B", 190.0), ("C", 240.0), ("D", 290.0), ("E", 363.0), ("F", 435.0), ("G", inf)],
    "Belgium Flanders": [("A+", 0.0), ("A", 100.0), ("B", 200.0), ("C", 300.0), ("D", 400.0), ("E", 500.0), ("F", inf)],
    "Netherlands": [("A++++", 0.0), ("A+++", 50.0), ("A++", 75.0), ("A+", 105.0), ("A", 160.0), ("B", 190.0), ("C", 250.0), ("D", 290.0), ("E", 335.0), ("F", 380.0), ("G", inf)],
    "Romania": [("A", 115.0), ("B", 228.0), ("C", 344.0), ("D", 459.0)],
    "Slovakia": [("A", 140.0), ("B", 280.0), ("C", 420.0), ("D", 558.0)],
    "Portugal": [("A+", 25.0), ("A", 50.0), ("B", 75.0), ("B-", 100.0), ("C", 150.0), ("D", 200.0), ("E", 250.0), ("F", inf)],
    "Czech Republic": [("A", 50.0), ("B", 75.0), ("C", 100.0), ("D", 150.0), ("E", 200.0), ("F", 250.0), ("G", inf)],
}

COUNTRY_CONSUMPTION_THRESHOLDS["Greece"] = COUNTRY_CONSUMPTION_THRESHOLDS["Italy"]

COUNTRY_SCALE_NOTES = {
    "Portugal": "% of reference, not kWh/m²/year",
    "Czech Republic": "% of reference, not kWh/m²/year",
}

COUNTRY_ALIASES = {
    "greece": "Greece",
    "hellas": "Greece",
    "italy": "Italy",
    "italy old": "Italy",
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

AVAILABLE_TARGET_COUNTRIES = tuple(COUNTRY_CONSUMPTION_THRESHOLDS.keys())

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
    Prefer UTF-8 output so Greek EPC labels print correctly on Windows shells.
    """
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8")


def load_model(model_path: str | Path) -> Any:
    """
    Load the saved model with clearer error messages for common failures.
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


def normalize_target_country(target_country: str) -> str:
    """Return the canonical country/region name used by the mappings."""
    key = target_country.strip().lower()
    if key in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[key]

    allowed = ", ".join(AVAILABLE_TARGET_COUNTRIES)
    raise ValueError(
        f"Unknown target_country: {target_country!r}. "
        f"Available target countries are: {allowed}"
    )


def map_property_type(ui_label: str) -> str:
    """Map UI property type to the Greek label used by the model."""
    try:
        return PROPERTY_TYPE_MAP[ui_label]
    except KeyError as exc:
        allowed = ", ".join(sorted(PROPERTY_TYPE_MAP.keys()))
        raise ValueError(
            f"Unknown property_type_ui option: {ui_label!r}. "
            f"Allowed values are: {allowed}"
        ) from exc


def energy_consumption_to_source_epc(target_country: str, energy_consumption: float) -> str:
    """
    Convert energy consumption to the local/source-country EPC class.

    For most countries the value is kWh/m²/year. For Portugal and Czech
    Republic it is % of reference, matching the Excel scale.
    """
    if energy_consumption < 0:
        raise ValueError("energy_consumption must be non-negative.")

    canonical_country = normalize_target_country(target_country)
    thresholds = COUNTRY_CONSUMPTION_THRESHOLDS[canonical_country]

    for epc_class, upper_bound in thresholds:
        if energy_consumption <= upper_bound:
            return epc_class
    return thresholds[-1][0]


def map_source_epc_to_italy(target_country: str, source_epc_class: str) -> str:
    """Map a source-country EPC class to Italy old-scale EPC."""
    canonical_country = normalize_target_country(target_country)
    class_map = COUNTRY_EPC_TO_ITALY[canonical_country]
    normalized_epc = source_epc_class.strip().upper()

    try:
        return class_map[normalized_epc]
    except KeyError as exc:
        allowed = ", ".join(class_map.keys())
        raise ValueError(
            f"Cannot map source EPC class {source_epc_class!r} for "
            f"{canonical_country!r}. Allowed classes are: {allowed}"
        ) from exc


def map_italy_epc_to_greek(italy_epc_class: str) -> str:
    """Map Italy old-scale EPC to Greek EPC."""
    try:
        return ENERGY_CLASS_MAP_ITALY_TO_GREECE[italy_epc_class]
    except KeyError as exc:
        allowed = ", ".join(ENERGY_CLASS_MAP_ITALY_TO_GREECE.keys())
        raise ValueError(
            f"Cannot map Italy EPC class {italy_epc_class!r} to Greek EPC. "
            f"Allowed Italy classes are: {allowed}"
        ) from exc


def resolve_epc_from_consumption(
    *,
    target_country: str,
    energy_consumption: float,
) -> dict[str, str]:
    """
    Full EPC resolution chain:
      energy consumption -> source EPC -> Italy EPC -> Greek EPC.
    """
    canonical_country = normalize_target_country(target_country)
    source_epc = energy_consumption_to_source_epc(canonical_country, energy_consumption)
    italy_epc = map_source_epc_to_italy(canonical_country, source_epc)
    greek_epc = map_italy_epc_to_greek(italy_epc)

    return {
        "target_country": canonical_country,
        "source_epc_class": source_epc,
        "italy_epc_class": italy_epc,
        "greek_epc_class": greek_epc,
        "model_epc_class": greek_epc,
    }


def build_input_row(
    *,
    target_country: str,
    energy_consumption: float,
    lat: float,
    lng: float,
    floor_area: float,
    construction_year: int,
    floor_number: float,
    property_type_ui: str,
    renovated_last_5_years: bool,
    number_of_floors: int,
) -> tuple[pd.DataFrame, dict[str, str]]:
    """Build a single-row DataFrame with the columns the model expects."""
    current_year = datetime.now().year
    building_age = current_year - construction_year

    property_type_greek = map_property_type(property_type_ui)
    epc_info = resolve_epc_from_consumption(
        target_country=target_country,
        energy_consumption=energy_consumption,
    )

    data: dict[str, list[Any]] = {
        "floor_area": [floor_area],
        "building_age": [building_age],
        "floor_number": [floor_number],
        "lat": [lat],
        "lng": [lng],
        "energy_class": [epc_info["model_epc_class"]],
        "type": [property_type_greek],
        "renovated_last_5_years": [renovated_last_5_years],
        "number_of_floors": [number_of_floors],
    }

    return pd.DataFrame(data), epc_info


def predict_price_per_sqm(model: Any, input_row: pd.DataFrame) -> float:
    """Run the model and return the predicted price per square meter."""
    return float(model.predict(input_row)[0])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Predict property price from energy consumption using country-specific EPC thresholds."
    )
    parser.add_argument(
        "--target-country",
        default="Italy",
        help="Country whose EPC consumption scale should be used. Aliases such as 'czechia' and 'brussels' are accepted.",
    )
    parser.add_argument(
        "--energy-consumption",
        type=float,
        default=85.0,
        help="Energy consumption value. Usually kWh/m²/year; for Portugal and Czech Republic this is % of reference.",
    )
    parser.add_argument("--lat", type=float, default=37.981)
    parser.add_argument("--lng", type=float, default=23.728)
    parser.add_argument("--floor-area", type=float, default=85.0)
    parser.add_argument("--construction-year", type=int, default=1985)
    parser.add_argument("--floor-number", type=parse_floor_number, default=np.nan)
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

    canonical_target_country = normalize_target_country(args.target_country)
    scale_note = COUNTRY_SCALE_NOTES.get(canonical_target_country, "kWh/m²/year")

    print("=== Available target countries ===")
    print("  " + ", ".join(AVAILABLE_TARGET_COUNTRIES))
    print()

    print("=== Raw input ===")
    print(f"  target_country: {canonical_target_country}")
    print(f"  energy_consumption: {args.energy_consumption}")
    print(f"  energy_consumption_scale: {scale_note}")
    print(f"  model_path: {MODEL_PATH}")
    print(f"  lat: {args.lat}")
    print(f"  lng: {args.lng}")
    print(f"  floor_area: {args.floor_area}")
    print(f"  construction_year: {args.construction_year}")
    print(f"  floor_number: {args.floor_number}")
    print(f"  property_type_ui: {args.property_type_ui}")
    print(f"  renovated_last_5_years: {args.renovated_last_5_years}")
    print(f"  number_of_floors: {args.number_of_floors}")
    print()

    row, epc_info = build_input_row(
        target_country=args.target_country,
        energy_consumption=args.energy_consumption,
        lat=args.lat,
        lng=args.lng,
        floor_area=args.floor_area,
        construction_year=args.construction_year,
        floor_number=args.floor_number,
        property_type_ui=args.property_type_ui,
        renovated_last_5_years=args.renovated_last_5_years,
        number_of_floors=args.number_of_floors,
    )

    print("=== EPC resolution ===")
    print(f"  source_country_epc_class: {epc_info['source_epc_class']}")
    print(f"  italy_old_scale_epc_class: {epc_info['italy_epc_class']}")
    print(f"  greek_epc_class: {epc_info['greek_epc_class']}")
    print(f"  model_energy_class: {epc_info['model_epc_class']}")
    print()

    print("=== Model row ===")
    print(row.to_string(index=False))
    print()

    print(f"Loading model from: {MODEL_PATH}")
    model = load_model(MODEL_PATH)
    print("Model loaded successfully.\n")

    y_pred = predict_price_per_sqm(model, row)
    total_price = y_pred * row["floor_area"].iloc[0]

    print("=== Prediction result ===")
    print(f"  price_per_sqm: {y_pred:.2f} €")
    print(f"  total_price:   {total_price:.2f} €")


if __name__ == "__main__":
    main()
