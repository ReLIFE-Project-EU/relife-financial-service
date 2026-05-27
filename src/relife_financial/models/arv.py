"""
Pydantic models for After Renovation Value (ARV) endpoint.

This module defines the data contracts (request/response structure) for the
property price prediction API based on a trained LightGBM model.

Models:
    - PropertyType: Enum defining allowed property types
    - ARVRequest: Input parameters for property valuation
    - ARVValueSnapshot: Price prediction for a single energy state
    - ARVUplift: Monetary and percentage increase between two states
    - ARVResponse: Full response with before/after values and uplift
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
            target_country: Country whose EPC scale applies (e.g. "Italy", "Austria", "Germany")
            energy_consumption_before: Pre-renovation energy consumption. If provided,
                enables before/after comparison and uplift calculation.
            energy_consumption_after: Post-renovation energy consumption (required).
                For most countries: kWh/m²/year. For Portugal and Czech Republic: % of reference.
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
    target_country: str = Field(
        ...,
        description=(
            "Country whose national EPC scale applies to this property. "
            "Supported values: Greece, Italy, Croatia, Spain, Portugal, Czech Republic, "
            "Germany, France, Austria, Netherlands, Belgium Brussels, Belgium Wallonia, "
            "Belgium Flanders, Luxembourg Flats, Luxembourg Houses, Denmark, Norway, "
            "Finland, Bulgaria, Romania, Slovakia. "
            "Country aliases (e.g. 'hellas', 'flanders', 'brussels') are also accepted."
        ),
        examples=["Italy", "Austria", "Germany"]
    )

    energy_consumption_before: Optional[float] = Field(
        default=None,
        gt=0,
        description=(
            "Pre-renovation energy consumption. When provided together with "
            "energy_consumption_after, the response includes a before/after comparison "
            "and uplift calculation. Same unit as energy_consumption_after."
        ),
        examples=[220.0, 300.0]
    )

    energy_consumption_after: float = Field(
        ...,
        gt=0,
        description=(
            "Post-renovation energy consumption of the property. "
            "For most countries: kWh/m²/year. "
            "For Portugal and Czech Republic: % of reference consumption."
        ),
        examples=[85.0, 150.0]
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


class ARVValueSnapshot(BaseModel):
    """
    Predicted property value for a single energy state (before or after renovation).
    """
    price_per_sqm: float = Field(
        ...,
        description="Predicted price per square meter (€/m²).",
        examples=[980.00]
    )
    total_price: float = Field(
        ...,
        description="Total predicted property value (€).",
        examples=[83300.00]
    )
    greek_epc_class: str = Field(
        ...,
        description="Resolved Greek EPC class used as model input.",
        examples=["Η", "Ε", "Α+"]
    )
    epc_resolution: dict = Field(
        default_factory=dict,
        description="EPC resolution chain: source EPC → Italy EPC → Greek EPC.",
        examples=[{"target_country": "Italy", "source_epc_class": "G", "italy_epc_class": "G", "greek_epc_class": "Η"}]
    )


class ARVUplift(BaseModel):
    """
    Monetary and percentage value increase from pre- to post-renovation state.
    """
    price_increase: float = Field(
        ...,
        description="Absolute increase in total property value (€). Can be negative.",
        examples=[21717.50]
    )
    price_increase_pct: float = Field(
        ...,
        description="Percentage increase in total property value. Can be negative.",
        examples=[26.07]
    )


class ARVResponse(BaseModel):
    """
    Response model for After Renovation Value prediction.

    When only energy_consumption_after is provided, only `after` is populated.
    When both energy_consumption_before and energy_consumption_after are provided,
    `before`, `after`, and `uplift` are all populated.
    """
    after: ARVValueSnapshot = Field(
        ...,
        description="Predicted property value using post-renovation energy consumption."
    )
    before: Optional[ARVValueSnapshot] = Field(
        default=None,
        description="Predicted property value using pre-renovation energy consumption. "
                    "Only present when energy_consumption_before was provided."
    )
    uplift: Optional[ARVUplift] = Field(
        default=None,
        description="Value increase from before to after renovation. "
                    "Only present when energy_consumption_before was provided."
    )
    floor_area: float = Field(
        ...,
        description="Floor area used in calculations (m²).",
        examples=[85.0]
    )
    metadata: dict = Field(
        default_factory=dict,
        description="Prediction details: model file, timestamp, building age, input echo."
    )
