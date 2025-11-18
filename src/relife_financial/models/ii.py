#Define pydantic models for II calculations
from typing import List, Optional
from pydantic import BaseModel, Field

class IIRequest(BaseModel):


    capex: float
    interest_rate:float
    loan_term: float
    loan_amount: float
    subsidy: float


class IIResponse(BaseModel):
    ii: float
    input: IIRequest


