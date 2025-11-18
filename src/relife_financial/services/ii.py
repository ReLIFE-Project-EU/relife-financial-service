#II business logic
from typing import List

def calculate_ii(
    capex: float,
    interest_rate: float = 0.0,
    loan_term: float = 0.0,
    loan_amount: float = 0.0,
    subsidy: float = 0.0,
) -> float:
    """
    Calculate the Initial Investment (II) based on provided inputs.

    - Case 1: Only CAPEX
    - Case 2: CAPEX with Subsidy
    - Case 3: CAPEX with Loan
    - Case 4: CAPEX with Subsidy and Loan

    Missing values (like loan or subsidy) are treated as 0.
    """

    if subsidy == 0 and loan_amount == 0:
        # Case 1: Only CAPEX
        ii = capex

    elif subsidy > 0 and loan_amount == 0:
        # Case 2: CAPEX with Subsidy
        ii = capex - subsidy

    elif loan_amount > 0 and subsidy == 0:
        # Case 3: CAPEX with Loan
        ii = capex - loan_amount

    elif loan_amount > 0 and subsidy > 0:
        # Case 4: CAPEX with Subsidy and Loan
        ii = capex - subsidy - loan_amount

    else:
        # Fallback 
        ii = capex

    return ii