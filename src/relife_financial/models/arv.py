"""
Pydantic models for After Renovation Value (ARV) endpoint.

This module defines the data contracts (request/response structure) for the
property price prediction API based on a trained LightGBM model.

Models:
    - PropertyType: Enum defining allowed property types
    - EnergyClass: Enum defining valid energy efficiency classes
    - ARVRequest: Input parameters for property valuation
    - ARVResponse: Output structure with predicted prices
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from enum import Enum


class PropertyType(str, Enum):
    """
    Property type classifications.
    
    These English labels are mapped internally to Greek labels
    used by the trained model.
    """
    LOFT = "Loft"
    STUDIO = "Studio / Bedsit"
    VILLA = "Villa"
    APARTMENT = "Apartment"
    BUILDING = "Building"
    OTHER = "Other"
    MAISONETTE = "Maisonette"
    DETACHED_HOUSE = "Detached House"
    APARTMENT_COMPLEX = "Apartment Complex"


class EnergyClass(str, Enum):
    """
    Energy Performance Certificate (EPC) classes.
    
    Ordered from worst (Η) to best (Α+) energy efficiency.
    Greek labels as used in the Greek property market.
    """
    H = "Η"  # Worst
    Z = "Ζ"
    E = "Ε"
    D = "Δ"
    G = "Γ"
    B = "Β"
    B_PLUS = "Β+"
    A = "Α"
    A_PLUS = "Α+"  # Best


class ARVRequest(BaseModel):
    """
    Request model for After Renovation Value (ARV) prediction.
    
    Defines all property characteristics needed for price prediction
    using the trained LightGBM model.
    
    Attributes:
        Location:
            lat: Latitude coordinate (decimal degrees)
            lng: Longitude coordinate (decimal degrees)
        
        Physical Characteristics:
            floor_area: Usable floor area in square meters
            construction_year: Year the building was constructed
            floor_number: Floor level where property is located (can be None for houses)
            number_of_floors: Total floors in the building
            property_type: Type of property (Apartment, Villa, etc.)
        
        Energy Performance:
            energy_class: Current/predicted EPC label after renovation
            renovated_last_5_years: Whether property was recently renovated
    """
    
    # ─────────────────────────────────────────────────────────────
    # Location Parameters
    # ─────────────────────────────────────────────────────────────
    lat: float = Field(
        ...,
        ge=-90,
        le=90,
        description="Latitude of the property location in decimal degrees.",
        examples=[37.981]
    )
    
    lng: float = Field(
        ...,
        ge=-180,
        le=180,
        description="Longitude of the property location in decimal degrees.",
        examples=[23.728]
    )
    
    # ─────────────────────────────────────────────────────────────
    # Physical Characteristics
    # ─────────────────────────────────────────────────────────────
    floor_area: float = Field(
        ...,
        gt=0,
        description="Usable floor area in square meters (m²).",
        examples=[85.0]
    )
    
    construction_year: int = Field(
        ...,
        ge=1800,
        le=2030,
        description="Year the building was originally constructed.",
        examples=[1985]
    )
    
    floor_number: Optional[int] = Field(
        default=None,
        description=(
            "Floor number where the property is located (0=ground floor, 1=first floor, etc.). "
            "Can be None for detached houses or when not applicable."
        ),
        examples=[2]
    )
    
    number_of_floors: int = Field(
        ...,
        ge=1,
        le=100,
        description="Total number of floors in the building.",
        examples=[5]
    )
    
    property_type: PropertyType = Field(
        ...,
        description="Type of property.",
        examples=["Apartment"]
    )
    
    # ─────────────────────────────────────────────────────────────
    # Energy Performance
    # ─────────────────────────────────────────────────────────────
    energy_class: EnergyClass = Field(
        ...,
        description=(
            "Energy Performance Certificate (EPC) class. "
            "This should be the AFTER renovation energy class (obtained from energy analysis API)."
        ),
        examples=["Β+"]
    )
    
    renovated_last_5_years: bool = Field(
        default=True,
        description=(
            "Whether the property has been renovated within the last 5 years. "
            "Typically True when evaluating post-renovation value."
        ),
        examples=[True]
    )
    
    @field_validator('floor_number')
    @classmethod
    def validate_floor_number(cls, v, info):
        """Validate floor_number is not greater than number_of_floors."""
        if v is not None and 'number_of_floors' in info.data:
            number_of_floors = info.data['number_of_floors']
            if v >= number_of_floors:
                raise ValueError(
                    f"floor_number ({v}) must be less than number_of_floors ({number_of_floors})"
                )
        return v


class ARVResponse(BaseModel):
    """
    Response model for After Renovation Value prediction.
    
    Contains the predicted property value after renovation based on
    the provided characteristics and energy efficiency class.
    
    Attributes:
        price_per_sqm: Predicted price per square meter (€/m²)
        total_price: Total predicted property value (€)
        floor_area: Echo of input floor area for reference (m²)
        energy_class: Echo of input energy class for reference
        metadata: Additional information about the prediction
    """
    
    price_per_sqm: float = Field(
        ...,
        description="Predicted price per square meter in euros.",
        examples=[1235.50]
    )
    
    total_price: float = Field(
        ...,
        description="Total predicted property value in euros (price_per_sqm × floor_area).",
        examples=[105017.50]
    )
    
    floor_area: float = Field(
        ...,
        description="Floor area used in calculation (m²).",
        examples=[85.0]
    )
    
    energy_class: str = Field(
        ...,
        description="Energy class used in prediction.",
        examples=["Β+"]
    )
    
    metadata: dict = Field(
        default_factory=dict,
        description="Additional metadata about the prediction (model version, timestamp, etc.).",
        examples=[{
            "model_version": "lgb_model.pkl",
            "prediction_timestamp": "2026-01-08T10:30:00Z",
            "building_age": 41
        }]
    )
