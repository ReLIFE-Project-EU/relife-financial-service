from typing import List
import numpy as np

def calculate_opex(
    energy_mix: List[float],
    energy_prices: List[float],
    maintenance_cost: float,
) -> float:


    opex = []
    for t in range(len(energy_mix)):
        if t < len(energy_prices):
            opex.append(energy_mix[t] * energy_prices[t]) 
        else:
            opex.append = 0  # Default to maintenance cost if no price data available

    opex = np.sum(opex) + maintenance_cost
    

    return float(opex)