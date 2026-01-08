# Financial Service KPI Scenarios & Monte Carlo Simulation

A compact Python toolkit for evaluating the financial performance of energy‑saving projects under multiple economic scenarios.  
It computes the **IRR, NPV, payback periods (PBP & DPP) and ROI** with or without loan financing, probabilities to results and **visualise** KPI ranges and distributions.

---

## Features

| Function | What it does |
|----------|--------------|
| `cash_flows()` | Builds a plain series of yearly operating cash flows. |
| `cash_flows_with_loan()` | Same as above, but layers in constant‑principal loan payments and interest. |
| `IRR()`, `NPV()` | Standard investment metrics via *numpy‑financial*. |
| `PBP()`, `DPP()` | Simple and discounted payback periods, with a safeguard that enforces **loan‑term ≥ PBP/DPP** when borrowing is used. |
| `ROI()` | Lifetime return on investment. |
| `build_market_distributions()` | Converts the **optimistic / moderate / pessimistic** paths (treated as P90 / P50 / P10) into full Normal or Lognormal distributions for each year.  
| `get_kpi_results()` | **Scenario & Monte Carlo engine** — samples from distributions for inflation, electricity prices, interest rates and discount rates. Returns KPI arrays and a summary of percentiles & success probabilities.|

---

## Installation

```bash
pip install numpy numpy-financial matplotlib
```

> The only non-standard package is **numpy-financial**; everything else is in the scientific Python stack.

---

## Quick-start examples

```python
# ── Project inputs ───────────────────────────────────────────
capex                  = 150_000      # € initial investment
annual_energy_savings  = 80_000       # kWh saved per year
annual_maint_cost      = 2_000        # € OPEX
lifetime_years         = 18

# ── Optional loan ────────────────────────────────────────────
loan_amount            = 90_000       # € borrowed
loan_term              = 8            # constant-principal loan, 8 years

# Run the scenario sweep
results = get_kpi_results(
    capex,
    annual_maint_cost,
    annual_energy_savings,
    lifetime_years,
    loan_amount,
    loan_term
)
```
---
The Monte Carlo summary reports for each KPI:

* **percentiles** (P5, P10, P25, median/P50, P75, P90, P95) <br/>
* **success probabilities** such as

  * `Pr(NPV > 0)` — probability the project creates value
  * `Pr(PBP < lifetime)` and `Pr(DPP < lifetime)`

