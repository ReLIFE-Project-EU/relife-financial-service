#NPV business logic
from typing import List

def calculate_npv(
    cash_flows: List[float],
    discount_rate: float,
    energy_savings: float,
    initial_investment: float,
    lifetime: int
) -> float:
    """
    Calculate the Net Present Value (NPV) for a series of cash flows.
    
    - **cash_flows**: List of floats, e.g. [-1000, 300, 400, 500]
    - **discount_rate**: Decimal, e.g. 0.1 for 10%
    - **energy_savings**: Float representing annual energy savings
    - **initial_investment**: Float representing the initial investment cost
    - **lifetime**: Integer representing the lifetime of the investment in years
    """
    npv = -initial_investment
    for t in range(1, lifetime + 1):
        # guard against index errors if cash_flows list is shorter than lifetime
        cf = cash_flows[t-1] if t-1 < len(cash_flows) else 0.0
        npv += (cf + energy_savings) / ((1 + discount_rate) ** t)
    
    return npv