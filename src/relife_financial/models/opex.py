#Define pydantic models for II calculations
from typing import List, Optional
from pydantic import BaseModel, Field

class OPEXRequest(BaseModel):


    energy_mix: List[float]
    energy_prices: List[float]
    maintenance_cost: float


class OPEXResponse(BaseModel):
    opex: float
    input: OPEXRequest


