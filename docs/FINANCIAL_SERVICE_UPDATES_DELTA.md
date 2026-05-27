# Financial Service Updates — Delta Analysis

This document compares the updated calculation logic in `Financial Service Updates/` against the current implementation deployed in the APIs. It covers both the **Risk Assessment** and **ARV** modules.

---

## Part 1 — Risk Assessment

### Source files compared

| | Current | Updated |
|---|---|---|
| File | `Indicator Modules/simulation_engine.py` | `Financial Service Updates/Risk Assessment/financial_simulation_with_schemes.py` |

---

### Change 1 — Financing Schemes (Major)

**Current API**: supports exactly two financing modes via a runtime branch:
- `cash_flows()` — all-equity
- `cash_flows_with_loan()` — bank loan (with incentive parameters)

**Updated code**: introduces a full **scheme dispatch architecture** supporting 12 distinct financing structures. Each scheme has its own cash-flow function and a required set of additional inputs. The central entry point `get_kpi_results()` accepts a `schemes` list and runs the simulation for each scheme in parallel, returning results keyed by scheme type.

| Scheme key | Description | New inputs required |
|---|---|---|
| `equity` | All-equity (no debt) | — |
| `bank_loan` | Traditional bank loan | `loan_amount`, `term_years` |
| `operational_lease` | Lessor covers CAPEX; client pays lease | `lease_payment`, `term_years` |
| `on_bill` | Repayment via electricity bill | `term_years`, `fixed_interest` |
| `green_bond_loan` | Green bond with amortising repayment | `gb_proceeds`, `term_years`, `fixed_interest`, `OM_green` |
| `green_bond_bullet` | Green bond with bullet repayment at maturity | `gb_proceeds`, `term_years`, `fixed_interest`, `OM_green` |
| `epc_guaranteed_savings` | Client finances via bank loan; ESCO compensates if savings fall short | `term_years`, `gs` (guaranteed savings €/year) |
| `epc_shared_savings` | ESCO covers CAPEX; savings shared for contract term | `p_ESCO` (ESCO share fraction), `term_years` |
| `epc_first_out` | ESCO covers CAPEX; client repays from savings until recovered | — |
| `royalty_crowdfunding` | Crowd finances in exchange for % of gross revenue | `loan_crowd`, `royalty_rate`, `term_years`, `fee_plat` |
| `lending_crowdfunding` | Crowd lends capital; fixed repayment like a loan | `loan_crowd`, `fixed_interest`, `term_years`, `fee_plat` |
| `equity_crowdfunding` | Crowd receives equity stake and % of profits | `equity_crowd`, `share_crowd`, `fee_plat` |

**Impact on API**: The current `RiskAssessmentRequest` must be extended to accept a `scheme` (or `schemes`) parameter with scheme-specific details. The response must return per-scheme KPI results.

---

### Change 2 — Incentive Parameters Removed

**Current API**: `cash_flows()` and `cash_flows_with_loan()` both accept:
- `upfront_incentive_percentage`
- `lifetime_incentive_amount`
- `lifetime_incentive_years`

**Updated code**: these parameters are **absent** from the updated `cash_flows()` and `cash_flows_with_loan()` functions. Incentive-type financing is now expressed implicitly through the scheme structure (e.g., `epc_first_out` and `epc_shared_savings` model ESCO-financed arrangements; `operational_lease` models zero-CAPEX scenarios).

**Impact on API**: A decision is required on whether to retain incentive parameters alongside the new scheme architecture, or replace them entirely with scheme-based equivalents.

---

### Change 3 — Fifth Stochastic Variable: Energy Savings Uncertainty (New)

**Current API**: `annual_energy_savings` is treated as a **fixed input** — the user-provided value is used directly in every simulation iteration. Only four market variables are randomised (inflation, electricity price, loan interest rate, discount rate).

**Updated code**: adds a **fifth stochastic dimension** via `build_energy_savings_factor_distribution()`. In every Monte Carlo iteration, `annual_energy_savings` is multiplied by a random factor drawn from:

$$\text{factor} \sim \mathcal{N}(\mu=1.0, \sigma) \quad \text{where } \sigma = \frac{1 - (1 - \text{downside\_at\_p10})}{Z_{90}}$$

Default: `downside_at_p10 = 0.30`, meaning the P10 outcome corresponds to 70% of the estimated savings (i.e., a 30% shortfall at the pessimistic end).

**Impact on API**: KPI distributions will be wider than current results. This models real-world uncertainty in energy performance — a critical addition for honest risk communication.

---

### Change 4 — Cash Flow Functions Return Inflows and Outflows Separately

**Current API**: all `cash_flows_*()` functions return a single `list[float]` of *net* cash flows.

**Updated code**: all cash-flow functions return a **3-tuple**: `(flows, inflows, outflows)`, where:
- `flows` = net cash flows per year (as before)
- `inflows` = gross revenue per year (energy savings × electricity price)
- `outflows` = total costs per year (OPEX + debt service + scheme-specific charges)

This enables the simulation engine to output year-by-year **percentile distributions** for inflows and outflows separately in `cashflow_distributions`.

**Impact on API**: the current service layer must be updated to unpack the new return tuple. It also unlocks richer cash-flow chart data for the frontend.

---

### Change 5 — Market Scenario Data Completely Updated

**Current API** uses conservative ECB 2% inflation target-based scenarios, calibrated to pre-2022 baselines:

```python
# Current: inflation converging towards ECB 2% target
'optimistic': [2.8, 2.4, 2.2, 2.0, 2.0, ...]
'moderate':   [3.0, 2.7, 2.5, 2.4, 2.3, ...]
'pessimistic':[3.5, 3.3, 3.2, 3.0, 2.9, ...]
```

**Updated code** uses data calibrated to post-2022 European market conditions with significantly higher starting values:

```python
# Updated: post-2022 calibrated data
'optimistic': [7.515, 9.293, 9.162, 9.021, ...]   # (higher macro optimism)
'moderate':   [6.11,  7.40,  6.96,  6.45,  ...]
'pessimistic':[4.70,  5.51,  4.77,  3.88,  ...]   # (lower but still elevated)
```

Electricity price scenarios are also new and explicit (currently absent from the hardcoded data in `run_simulation()`):

```python
# Updated electricity prices (€/kWh)
'optimistic': [0.271, 0.279, ..., 0.408]   # ~2.5%/year growth
'moderate':   [0.246, 0.254, ..., 0.383]
'pessimistic':[0.221, 0.229, ..., 0.358]
```

Interest rate scenarios now feature a downward trajectory (reflecting ECB rate cut path):

```python
# Updated interest rates (%)
'optimistic': [5.075, 3.750, 2.425, 1.312, ...]
'moderate':   [3.272, 1.947, 0.622, -0.49, ...]
'pessimistic':[1.470, 0.145, -1.17, -2.29, ...]
```

Discount rate scenarios are updated:

```python
# Updated (new)
{"optimistic": [0.02], "moderate": [0.06], "pessimistic": [0.08]}
```

**Impact on API**: existing users will see **different numerical results** for the same inputs due to changed market assumptions. This is an intentional recalibration, not a bug.

---

### Change 6 — P10/P90 Assignment Swap in `build_market_distributions()`

**Current API**: for inflation, interest, and discount, the mapping is:
```
optimistic scenario data → P10 (low end of distribution)
pessimistic scenario data → P90 (high end of distribution)
```
This was semantically: "optimistic = project-favourable = low inflation/rates".

**Updated code**: the assignment is **reversed** for inflation, interest, and discount:
```
pessimistic scenario data → P10 (low end)
optimistic scenario data  → P90 (high end)
```
This aligns with the new data labelling convention where "optimistic" means high macroeconomic activity (higher inflation, higher prices), consistent with how electricity prices are framed: higher prices = better revenue = optimistic for project owners. The P10/P90 ordering for electricity prices was already correct and is unchanged.

**Impact on API**: subtle change in how uncertainty is distributed around the median. Combined with the updated market data, this changes the shape of KPI distributions.

---

### Change 7 — New Output Structure (Per-Scheme, Histogram-First)

**Current API** `run_simulation()` returns:
```python
{
    "raw_data": {"irr": array, "npv": array, "pbp": array, "dpp": array, "roi": array},
    "summary": {"percentiles": {...}, "probabilities": {...}},
    "metadata": {...}
}
```

**Updated `get_kpi_results()`** returns a dict **keyed by scheme type**, and each scheme result contains:
```python
{
    "equity": {
        "scheme_id": 1,
        "summary": {
            "percentiles": {"IRR": {...}, "NPV": {...}, ..., "total_repayment": {...}},  # NEW: total_repayment
            "probabilities": {"Pr(NPV > 0)": ..., "Pr(PBP < Ny)": ..., "Pr(DPP < Ny)": ...},
            "disc_target_used": ...,
            "n_sims": ...
        },
        "kpi_histograms": {  # NEW: replaces matplotlib-based visualizations.py
            "NPV": {"bin_edges": [...], "feasible_counts": [...], "infeasible_counts": [...], "p10": ..., "p50": ..., "p90": ...},
            "IRR": {...}, "ROI": {...}, "PBP": {...}, "DPP": {...}
        },
        "cashflow_distributions": {  # NEW: year-by-year percentile bands
            "years": [0, 1, ..., N],
            "cash_flows": {"P5": [...], "P10": [...], ..., "P95": [...]},
            "inflows":    {"P5": [...], ..., "P95": [...]},
            "outflows":   {"P5": [...], ..., "P95": [...]}
        }
    },
    "bank_loan": {...},
    ...
}
```

Key new output fields:
- **`kpi_histograms`**: pre-computed histogram bin data (bin edges + feasible/infeasible counts) for each KPI. This replaces the server-side `matplotlib` chart generation in `visualizations.py` — the frontend renders charts from structured data instead of receiving base64 PNG images.
- **`cashflow_distributions`**: year-by-year percentile bands for cash flows, inflows, and outflows, enabling uncertainty waterfall/band charts.
- **`total_repayment`**: new KPI tracking total cost outflows over the project lifetime (scheme-dependent).

Raw 10,000-element arrays are **not returned** in the updated version — only pre-aggregated summaries. This reduces payload size significantly.

---

### Change 8 — Error Handling Overhaul

**Current API**: uses bare `try/except` blocks that silently return `np.nan` on failure. Errors propagate to the service layer as generic `RuntimeError`.

**Updated code**: introduces a structured exception hierarchy:

```python
FinancialSimulationError          # base
├── ExperimentConfigurationError  # no runnable scheme definitions
├── FinancialInputError           # missing/invalid numerical inputs
├── SchemeConfigurationError      # unsupported or misconfigured scheme
├── SimulationComputationError    # KPI/cash-flow computation failure
└── ResultPersistenceError        # results cannot be saved
```

Input validation is centralised through `_ensure()`, `_validate_finite_number()`, `_validate_series()`, and `_validate_flows()` helper functions, with clear error messages referencing the failing parameter by name.

---

### Change 9 — PBP/DPP Calculation Improvements

**Current API PBP**: uses a direct list iteration up to `project_lifetime` length. Can break if `flows` is shorter than expected.

**Updated PBP**: adds a `max_years = 100` safety cap, can extrapolate beyond `project_lifetime` by repeating the last known cash flow, and re-enables the `loan_term` floor constraint (currently disabled in the API with comment "Constraint removed: PBP now reflects true equity payback"). The new PBP also handles the edge case where initial investment ≤ 0.

The PBP/DPP loan floor is **re-enabled**: when a loan is active, payback period cannot be shorter than the loan term.

---

## Part 2 — ARV

### Source files compared

| | Current | Updated |
|---|---|---|
| Model | `data/lgb_model.pkl` | `Financial Service Updates/ARV/lgb_model_greece.pkl` |
| Logic | `services/arv.py` | `test_model_country_epc_to_italy.py`, `test_model_energy_consumption_to_greek_epc.py` |

---

### Change 1 — Multi-Country EPC Support (Major)

**Current API**: accepts only **Greek EPC labels** (`Η` through `Α+`) directly. The caller must know the post-renovation Greek EPC class.

**Updated code**: adds a **two-stage EPC normalisation pipeline** to support all major European national EPC scales:

```
Input → Source-country EPC class
    → Italy old-scale EPC (intermediate normalisation)
    → Greek EPC label (model input)
    → LightGBM prediction
```

Italy's scale is used as the intermediate step because the mapping table covers all supported countries via Italy. Supported countries:

| Region | Supported scales |
|---|---|
| Southern Europe | Greece, Italy, Croatia, Spain, Portugal |
| Western Europe | France, Germany, Netherlands, Belgium (Brussels / Wallonia / Flanders), Luxembourg (Flats / Houses) |
| Northern Europe | Denmark, Norway, Finland |
| Eastern Europe | Austria, Bulgaria, Romania, Slovakia, Czech Republic |

The API will need a new `target_country` input parameter to select which national EPC scale to interpret.

---

### Change 2 — Energy Consumption → EPC Derivation (New Input Mode)

**Current API**: requires the caller to know the EPC label (letter class). This label is expected to come from a separate energy analysis API.

**Updated code** (`test_model_energy_consumption_to_greek_epc.py`): adds a conversion pipeline:

```
energy consumption (kWh/m²/year)
    → source-country EPC class (via threshold tables)
    → Italy EPC
    → Greek EPC
    → model prediction
```

Country-specific energy consumption threshold tables are provided for all 20 supported countries. For Portugal and Czech Republic, the input is `% of reference` rather than `kWh/m²/year`.

This enables the ARV to be called **directly with energy performance data** from an energy simulation tool, without requiring a prior EPC classification step.

**Impact on API**: the `ARVRequest` model should be extended to optionally accept `energy_consumption` + `target_country` as an alternative to the current `energy_class` field.

---

### Change 3 — Updated Model File

The updated code loads `lgb_model_greece.pkl` (in `Financial Service Updates/ARV/`) rather than the current `lgb_model.pkl` (in `data/`). The model rename coincides with the multi-country expansion and likely reflects a retrained or re-serialised model. Functional equivalence for Greek inputs cannot be assumed without testing.

---

### Change 4 — EPC Mapping Completeness

The current service maps only the 9 Greek EPC labels to model inputs. The updated scripts additionally document:
- The full Greece ↔ Italy EPC mapping dictionary (bidirectional)
- Country group assignments for planned regional groupings:
  - Greece group: Spain, Portugal, Italy (old), Croatia
  - Austria group: Austria, Germany, Czech Republic, France, Belgium (all), Netherlands, Bulgaria, Slovakia, Romania
  - Finland group: Finland, Denmark, Norway, Luxembourg Houses

---

## Summary Table

| Change | Risk Assessment | ARV | Priority |
|---|---|---|---|
| Multiple financing schemes | Major new feature | — | High |
| Incentive parameters removed | Needs reconciliation | — | High |
| Energy savings uncertainty (5th stochastic variable) | New stochastic dimension | — | High |
| Cash flows return inflows + outflows separately | Breaking change in function signatures | — | High |
| Updated market scenario data | New calibration (post-2022) | — | Medium |
| P10/P90 label swap in `build_market_distributions()` | Subtle distribution change | — | Medium |
| New output structure (per-scheme, histogram-first) | Major API response change | — | High |
| Structured exception hierarchy | Internal robustness | — | Medium |
| PBP/DPP improvements | Accuracy edge cases | — | Low |
| Multi-country EPC support | — | Major new feature | High |
| Energy consumption → EPC | — | New input mode | High |
| Updated model file | — | Potentially different predictions | Medium |
