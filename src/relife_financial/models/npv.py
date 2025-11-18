#Define pydantic models for NPV calculations
from typing import List, Optional
from pydantic import BaseModel, Field

class NPVRequest(BaseModel):

    cash_flows: List[float]
    discount_rate:float
    energy_savings: float
    initial_investment: float
    lifetime: int


class NPVResponse(BaseModel):
    npv: float
    input: NPVRequest
