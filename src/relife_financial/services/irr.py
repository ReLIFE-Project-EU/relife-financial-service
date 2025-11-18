from typing import List
import numpy as np


def calculate_irr(
        
        capex: float = 0.0,
        interest_rate: float = 0.0,
        loan_term: float = 0.0,
        loan_amount: float = 0.0,
        subsidy: float = 0.0,
        energy_savings: float = 0.0,
        energy_mix: List[float] = None,
        energy_prices: List[float] = None,
        maintenance_cost: float = 0.0,
        other_outflows: float = 0.0,
        project_lifetime: float = 20.0,  # Default project lifetime
) -> float:
    
    if energy_mix is None:
        energy_mix = []

    if energy_prices is None:
        energy_prices = []

    # Calculate OPEX
    opex = []
    for t in range(len(energy_mix)):
        if t < len(energy_prices):
            opex.append(energy_mix[t] * energy_prices[t])
        else:
            opex.append(maintenance_cost)  # Default to maintenance cost if no price data available

    opex_total = np.sum(opex) + maintenance_cost

    # Calculate Initial Investment (II)
    ii = capex - subsidy - loan_amount if (subsidy > 0 or loan_amount > 0) else capex

    if ii==0:
        irr =0
    else:
    # Calculate IRR using a simple formula (this is a placeholder, actual IRR calculation may require more complex financial modeling)
     irr = (energy_savings - opex_total - other_outflows) / ii

    irr=float(irr)

    return irr
