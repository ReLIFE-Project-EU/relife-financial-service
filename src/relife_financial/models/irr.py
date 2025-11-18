#Define pydantic models for II calculations
from typing import List, Optional
from pydantic import BaseModel, Field

class IRRRequest(BaseModel):
        capex: float
        interest_rate: float
        loan_term: float
        loan_amount: float
        subsidy: float
        energy_savings: float
        energy_mix: List[float]
        energy_prices: List[float]
        maintenance_cost: float
        other_outflows: float
        project_lifetime: float


class IRRResponse(BaseModel):
    irr: float
    input: IRRRequest


