from typing import List
import numpy as np


def calculate_roi(
        capex: float= 0.0,
        interest_rate: float= 0.0,
        loan_term: float= 0.0,
        loan_amount: float= 0.0,
        subsidy: float= 0.0,
        energy_savings: float= 0.0,
        energy_mix: List[float]=None,
        energy_prices: List[float]=None,
        maintenance_cost: float= 0.0,
        other_outflows: float= 0.0,
)-> float: 
    


    if energy_mix is None:
        energy_mix=[]

    if energy_prices is None:
        energy_prices=[]
    #Calculate roi
    #first calucalte opex and initial investment

    #OPEX

    opex = []

    for t in range(len(energy_mix)):
        if t < len(energy_prices):
            opex.append(energy_mix[t] * energy_prices[t]) 
        else:
            opex.append(0)  # Default to maintenance cost if no price data available

    opex = np.sum(opex) + maintenance_cost
    opex=float(opex)  # Ensure opex is a float

    #Initial Investment (II)

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


#ROI
    
    net_profit= energy_savings-opex-other_outflows
    if ii == 0:
        roi = 0.0
    else:
     roi = (net_profit-ii)/ii *100

    roi=float(roi)

    return roi