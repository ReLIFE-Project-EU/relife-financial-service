# ReLIFE Financial Service — API Architecture Reference

## Overview

The **ReLIFE Financial Service** is a FastAPI-based microservice that exposes two core calculation APIs as part of the broader [ReLIFE](https://relife-project.eu/) European LIFE programme. The project supports decision-making for deep energy renovation in the residential sector by providing standardised financial and property-value calculations.

The service is structured as a layered architecture: HTTP routes receive requests, delegate to a service layer that orchestrates business logic, which in turn calls purpose-built calculation modules. Authentication (Keycloak JWT) and data persistence (Supabase) are handled separately and are optional for the calculation endpoints.

```
HTTP Request
    │
    ▼
routes/          ← FastAPI router (input/output contracts, HTTP status codes)
    │
    ▼
services/        ← Business logic orchestration (parameter validation, result formatting)
    │
    ▼
Indicator Modules/   ← Reusable calculation engine (Monte Carlo, KPIs, visualizations)
                         [Risk Assessment only]
    OR
data/lgb_model.pkl   ← Trained LightGBM model
                         [ARV only]
```

---

## API 1 — Risk Assessment (`POST /risk-assessment`)

### Purpose

Runs a **Monte Carlo simulation (10,000 scenarios)** to assess the financial risk and return of an energy retrofit investment. Given a capital expenditure, expected energy savings, and optional loan/incentive parameters, it returns probabilistic distributions of standard financial KPIs.

This API is intended to be called *after* an energy consumption API has estimated `annual_energy_savings`.

### Module Chain

```
routes/risk_assessment.py
    └── assess_project_risk()
            │
            ▼
        services/risk_assessment.py
            └── perform_risk_assessment()
                    │
                    └── Indicator Modules/simulation_engine.py
                            └── get_kpi_results()                           ← single entry point for all schemes
                                    ├── build_energy_savings_factor_distribution()  ← Normal stochastic savings factor
                                    ├── build_market_distributions()                ← per-year price/rate distributions
                                    │
                                    ├── cash_flows()                               ← equity (family 1)
                                    ├── cash_flows_with_loan()                     ← bank_loan (family 2)
                                    ├── cash_flows_green_bond_loan()               ← green_bond_loan (family 2)
                                    ├── cash_flows_green_bond_bullet()             ← green_bond_bullet (family 2)
                                    ├── cash_flows_on_bill_financing()             ← on_bill (family 3)
                                    ├── cash_flows_operational_leasing()           ← operational_lease (family 3)
                                    ├── cash_flows_epc_shared_savings()            ← epc_shared_savings (family 3)
                                    ├── cash_flows_first_out_contract()            ← epc_first_out (family 3)
                                    ├── cash_flows_epc_guaranteed_savings()        ← epc_guaranteed_savings (family 3)
                                    ├── cash_flows_lending_crowdfunding()          ← lending_crowdfunding (family 4)
                                    ├── cash_flows_royalty_crowdfunding()          ← royalty_crowdfunding (family 4)
                                    ├── cash_flows_equity_crowdfunding()           ← equity_crowdfunding (family 4)
                                    │
                                    ├── IRR()                                      ← Internal Rate of Return
                                    ├── NPV()                                      ← Net Present Value
                                    ├── PBP()                                      ← Simple Payback Period
                                    ├── DPP()                                      ← Discounted Payback Period
                                    ├── ROI()                                      ← Return on Investment
                                    ├── _build_kpi_histogram_payload()             ← histogram bins + counts per KPI
                                    └── (cash-flow fan chart built inline)         ← P5/P10/P50/P90/P95 per year
```

### Input Model — `RiskAssessmentRequest`

| Parameter | Type | Required | Description |
|---|---|---|---|
| `capex` | `float` | Yes | Capital expenditure in € |
| `annual_energy_savings` | `float` | Yes | kWh/year saved (from energy API) |
| `annual_maintenance_cost` | `float` | Yes | Annual O&M cost in € |
| `project_lifetime` | `int` (1–30) | Yes | Evaluation horizon in years |
| `schemes` | `list[SchemeInput]` | Yes | One or more financing schemes (discriminated union on `scheme_type`). 12 types across 4 families. See [RISK_ASSESSMENT_API_FRONTEND_CHANGELOG.md](RISK_ASSESSMENT_API_FRONTEND_CHANGELOG.md) for the full parameter table |
| `output_level` | `enum` | Yes | `private` / `professional` / `public` / `complete` |
| `indicators` | `list[str]` | No (default all) | Any subset of `["IRR","NPV","PBP","DPP","ROI"]` |

> **Note:** `output_level` is set by the *frontend tool*, not the end-user. It controls how much detail is returned per scheme.

### Monte Carlo Simulation — How It Works

`get_kpi_results()` (in `simulation_engine.py`) accepts a list of `(scheme_type, details)` tuples and runs the following steps **for each scheme** across 10,000 Monte Carlo draws:

1. **Sample market variables** using `build_market_distributions()`, which converts three economic scenario paths (optimistic / moderate / pessimistic) into per-year probability distributions:
   - **Inflation rate** — Normal distribution; optimistic=low, pessimistic=high (ECB-calibrated)
   - **Electricity price** — Lognormal distribution; optimistic=high, pessimistic=low (high prices = more revenue = favourable)
   - **Loan interest rate** — Normal distribution
   - **Discount rate** — drawn per simulation to sample NPV at realistic cost-of-capital

2. **Sample energy savings factor** using `build_energy_savings_factor_distribution()` — a Normal multiplicative factor applied to `annual_energy_savings` (P50=1.0×, P10=0.70×). Captures real-world uncertainty about whether predicted savings are actually achieved.

3. **Generate cash flows** by dispatching to the appropriate scheme function from `CASHFLOW_FUNCTIONS` dict. Each function returns `(cash_flows, inflows, outflows)` arrays of length `project_lifetime + 1`, with Year 0 at index 0. All 12 scheme types are supported.

4. **Calculate KPIs** for each simulated scenario:
   - `IRR()` — discount rate that makes NPV = 0
   - `NPV()` — present value at a sampled discount rate
   - `PBP()` — years until undiscounted cumulative cash flows recover investment
   - `DPP()` — same as PBP but using discounted cash flows
   - `ROI()` — net profit / initial investment

5. **Build result payload** — computes P5/P10/P50/P90/P95 percentiles, success probabilities (`Pr(NPV>0)`, `Pr(PBP<T)`, `Pr(DPP<T)`), histogram bins for each KPI, and cash-flow fan chart data — all inside `get_kpi_results()`.

### Output — `RiskAssessmentResponse`

The response contains `results` (one entry per scheme) and a `metadata` object.

**`results` structure** — keyed by `scheme_type`:

```
{
  "results": {
    "<scheme_type>": {
      "scheme_id":     int,
      "scheme_family": str,   // self_financed | debt_financed | esco_zero_capex | crowdfunding
      "summary": {
        "percentiles":   { "IRR": {P5,P10,P50,P90,P95}, "NPV": {...}, ... },
        "probabilities": { "Pr(NPV > 0)": float, "Pr(PBP < Ty)": float, "Pr(DPP < Ty)": float },
        "disc_target_used": float,
        "n_sims": 10000
      },
      "cashflow_distributions": {
        "years":   [0, 1, ..., T],
        "cash_flows": { "P5":[...], "P10":[...], "P50":[...], "P90":[...], "P95":[...] },
        "inflows":  { ... },
        "outflows": { ... }
      },
      "kpi_histograms":  // professional / public / complete only
        { "NPV": {bin_edges, feasible_counts, infeasible_counts, p10, p50, p90, project_lifetime},
          "IRR": {...}, "ROI": {...}, "PBP": {...}, "DPP": {...} }
    }
  },
  "metadata": { capex, annual_energy_savings, ..., n_schemes, scheme_types, output_level, n_sims }
}
```

**Fields by `output_level`:**

| Data | `private` | `professional` | `public` | `complete` |
|---|:---:|:---:|:---:|:---:|
| `summary` (percentiles + probabilities) | ✅ | ✅ | ✅ | ✅ |
| `cashflow_distributions` | ✅ | ✅ | ✅ | ✅ |
| `kpi_histograms` | ❌ | ✅ | ✅ | ✅ |

### Financial Indicators Reference

| KPI | Symbol | Unit | Interpretation |
|---|---|---|---|
| Net Present Value | NPV | € | Total discounted profit over project lifetime. Positive = value created |
| Internal Rate of Return | IRR | fraction (e.g. 0.08 = 8%) | Equivalent annual return. Compare to cost of capital |
| Simple Payback Period | PBP | years | Years to recover investment from undiscounted cash flows |
| Discounted Payback Period | DPP | years | Years to recover investment accounting for time-value of money |
| Return on Investment | ROI | fraction | (Net profit − Investment) / Investment over full lifetime |

---

## API 2 — After Renovation Value (`POST /arv`)

### Purpose

Predicts the **market value of a property before and after energy renovation** based on physical characteristics, location, and energy consumption values. The model has been trained on **Greek property market data**.

This API accepts post-renovation energy consumption (and optionally pre-renovation) and resolves EPC classes internally through a three-stage chain before feeding the result into the LightGBM model. It is designed to receive energy consumption figures from a separate upstream energy analysis API.

> ⚠️ **Known limitation:** The LightGBM model is trained on Greek property market data only. For non-Greek users, absolute price figures (`price_per_sqm`, `total_price`) reflect Greek market levels and are not meaningful as local property values. Only `uplift.price_increase_pct` is a valid cross-border indicator. See [ARV_API_FRONTEND_CHANGELOG.md](ARV_API_FRONTEND_CHANGELOG.md) for details.

### Module Chain

```
routes/arv.py
    └── calculate_arv()
            │
            ▼
        services/arv.py
            └── predict_arv()
                    ├── resolve_epc_from_consumption()   ← full EPC chain (called once per consumption value)
                    │       ├── normalize_target_country()          ← canonicalises country name / aliases
                    │       ├── energy_consumption_to_source_epc()  ← consumption → national EPC class
                    │       ├── map_source_epc_to_italy()           ← national EPC → Italy old-scale
                    │       └── map_italy_epc_to_greek()            ← Italy EPC → Greek EPC (model input)
                    ├── _load_model()                ← lazy-loads data/lgb_model_greece.pkl (LightGBM pipeline)
                    ├── _build_input_dataframe()     ← assembles single-row feature DataFrame
                    │       └── _map_property_type() ← translates English labels → Greek labels
                    └── model.predict()              ← returns predicted price per m²
                    
    Called twice when energy_consumption_before is provided (once per snapshot).
```

### Input Model — `ARVRequest`

| Parameter | Type | Required | Description |
|---|---|---|---|
| `lat` | `float` (−90 to 90) | Yes | Property latitude |
| `lng` | `float` (−180 to 180) | Yes | Property longitude |
| `floor_area` | `float` | Yes | Usable floor area in m² |
| `construction_year` | `int` (1800–2030) | Yes | Year of construction |
| `floor_number` | `int` \| `None` | No | Floor level (0=ground). `None` for detached houses |
| `number_of_floors` | `int` (1–100) | Yes | Total floors in the building |
| `property_type` | `enum` | Yes | One of: `Apartment`, `Villa`, `Detached House`, `Maisonette`, `Studio / Bedsit`, `Loft`, `Building`, `Apartment Complex`, `Other` |
| `target_country` | `string` | Yes | Country whose national EPC scale applies. 21 countries supported plus aliases |
| `energy_consumption_after` | `float` | Yes | Post-renovation energy consumption (kWh/m²/year; % of reference for PT/CZ) |
| `energy_consumption_before` | `float` \| `None` | No | Pre-renovation consumption. Enables before/after comparison and uplift output |
| `renovated_last_5_years` | `bool` | No (default `true`) | Whether recently renovated |

### EPC Resolution Chain

For each consumption value supplied, the service runs a three-stage mapping before the model is called:

```
energy_consumption (kWh/m²/year or % of reference)
    │
    ▼  COUNTRY_CONSUMPTION_THRESHOLDS  (per-country threshold table)
    source-country EPC class  (e.g. Austria "B", Germany "C")
    │
    ▼  COUNTRY_EPC_TO_ITALY  (21-country mapping table)
    Italy old-scale EPC class  (A+ through G)
    │
    ▼  ENERGY_CLASS_MAP_ITALY_TO_GREECE  (8-entry dict)
    Greek EPC class  (Α+ through Η)  ← model input
```

**Supported countries:** Greece, Italy, Croatia, Spain, Portugal, Czech Republic, Germany, France, Austria, Netherlands, Belgium Brussels, Belgium Wallonia, Belgium Flanders, Luxembourg Flats, Luxembourg Houses, Denmark, Norway, Finland, Bulgaria, Romania, Slovakia.

> Greece has no official consumption thresholds and borrows Italy's scale as an approximation.

### Model Details

- **Algorithm:** LightGBM (gradient-boosted decision trees)
- **Target:** Price per square meter (€/m²)
- **Input features:** `floor_area`, `building_age` (computed as `current_year − construction_year`), `floor_number`, `lat`, `lng`, `number_of_floors`, `energy_class` (resolved Greek EPC), `type` (Greek property category label), `renovated_last_5_years`
- **Training data:** Greek residential property market
- **File:** `src/relife_financial/data/lgb_model_greece.pkl` (loaded once, singleton pattern)
- **Property type mapping:** English UI labels are mapped internally to Greek labels as used in the training data

### Output — `ARVResponse`

| Field | Type | Present when | Description |
|---|---|---|---|
| `after` | `ARVValueSnapshot` | Always | Prediction using post-renovation energy consumption |
| `before` | `ARVValueSnapshot` \| `null` | `energy_consumption_before` provided | Prediction using pre-renovation energy consumption |
| `uplift` | `ARVUplift` \| `null` | `energy_consumption_before` provided | Value increase from before → after |
| `floor_area` | `float` | Always | Echo of input floor area |
| `metadata` | `dict` | Always | Model file, timestamp, building age, EPC unit, input echo |

**`ARVValueSnapshot` fields:**

| Field | Type | Description |
|---|---|---|
| `price_per_sqm` | `float` | Predicted price per m² (€/m²) |
| `total_price` | `float` | `price_per_sqm × floor_area` (€) |
| `greek_epc_class` | `string` | Resolved Greek EPC class used by the model (e.g. `"Ε"`, `"Α+"`) |
| `epc_resolution` | `dict` | Full chain: `target_country`, `source_epc_class`, `italy_epc_class`, `greek_epc_class` |

**`ARVUplift` fields:**

| Field | Type | Description |
|---|---|---|
| `price_increase` | `float` | `after.total_price − before.total_price` (€). Can be negative |
| `price_increase_pct` | `float` | Percentage increase. Can be negative |

---

## Shared Infrastructure

### Authentication

Both endpoints use **optional JWT authentication** via Keycloak (`OptionalAuthenticatedUserDep`). If a valid Bearer token is provided, user details are logged for audit purposes. Unauthenticated requests are accepted.

### Application Entry Point

`src/relife_financial/app.py` — FastAPI application that registers all routers:

```
/              ← health/welcome
/health        ← health check
/auth/...      ← Keycloak auth routes
/examples/...  ← example request/response routes
/risk-assessment  ← Risk Assessment API
/arv              ← After Renovation Value API
```

### Module Origin — NTUA Source

The calculation logic in `Indicator Modules/` is a refactored version of the original research code in `NTUA_source/risk_assessment_v3.py`, developed by the National Technical University of Athens (NTUA) for the ReLIFE project. The refactoring separated the monolithic script into three focused modules:

| Module | Role |
|---|---|
| `simulation_engine.py` | Core Monte Carlo engine: 12 cash-flow functions (`CASHFLOW_FUNCTIONS` dispatch dict), `get_kpi_results()` orchestrator, KPI calculation, market distribution sampling, KPI histogram builder, cash-flow fan chart builder |
| `indicator_outputs.py` | Legacy utility module — no longer called by the main service. Kept for reference: extracts P50 medians, percentile tables, raw 10,000-element distributions, and success probability estimates |
| `visualizations.py` | Legacy chart-generation module — no longer called by the main service. Kept for reference: per-KPI distribution histograms, private cash-flow waterfall chart, multi-KPI dashboard |

---

## Example Requests

### Risk Assessment — Homeowner (equity financing)

```json
POST /risk-assessment
{
    "capex": 60000,
    "annual_energy_savings": 27400,
    "annual_maintenance_cost": 2000,
    "project_lifetime": 20,
    "output_level": "private",
    "schemes": [
        {"scheme_type": "equity"}
    ],
    "indicators": ["NPV", "PBP", "ROI", "IRR"]
}
```

### Risk Assessment — Energy Consultant (compare 3 schemes)

```json
POST /risk-assessment
{
    "capex": 60000,
    "annual_energy_savings": 27400,
    "annual_maintenance_cost": 2000,
    "project_lifetime": 20,
    "output_level": "professional",
    "schemes": [
        {"scheme_type": "equity"},
        {"scheme_type": "bank_loan", "loan_amount": 25000, "term_years": 15},
        {"scheme_type": "epc_shared_savings", "p_ESCO": 0.30, "term_years": 10}
    ],
    "indicators": ["IRR", "NPV", "PBP", "DPP", "ROI"]
}
```

### After Renovation Value — with before/after comparison

```json
POST /arv
{
    "lat": 37.981,
    "lng": 23.728,
    "floor_area": 85.0,
    "construction_year": 1985,
    "floor_number": 2,
    "number_of_floors": 5,
    "property_type": "Apartment",
    "target_country": "Italy",
    "energy_consumption_before": 220.0,
    "energy_consumption_after": 85.0,
    "renovated_last_5_years": true
}
```

---

## Key Design Decisions

| Decision | Rationale |
|---|---|
| Fixed seed (`seed=42`) in Monte Carlo | Ensures reproducible results for the same input |
| 10,000 simulations | Balances statistical accuracy with API response time |
| `output_level` set by frontend, not user | Prevents users from requesting unnecessarily large payloads |
| 12 financing schemes across 4 families | Single API call evaluates all requested schemes; enables client-side side-by-side comparison without multiple round trips |
| Discriminated union for scheme inputs | `scheme_type` discriminator allows clean Pydantic validation with per-scheme required fields; unknown or misconfigured schemes are rejected at request parsing time |
| Stochastic energy savings | `annual_energy_savings` is treated as a stochastic variable in each Monte Carlo draw; captures real-world uncertainty about whether predicted savings are actually achieved |
| KPI output built into `simulation_engine` | Percentiles, histograms, and fan-chart data are computed inside `get_kpi_results()`; the service layer is a thin orchestrator |
| LightGBM singleton loaded lazily | Avoids loading the model on every request; keeps startup fast |
| English → Greek property type mapping in ARV service | Decouples the API contract from the model's training data vocabulary |
| EPC resolved internally from consumption (Logic 2) | Upstream energy API outputs kWh/m²/year, not EPC labels; resolution happens server-side |
| Italy old-scale as EPC normalisation reference | Provides a consistent intermediate scale across 21 national EPC systems |
| `energy_consumption_before` optional | Single call returns both comparison and uplift; omitting it gives post-renovation value only |
| ARV absolute prices only meaningful for Greece | Model trained on Greek data; for other countries only `uplift.price_increase_pct` is cross-border valid |
| Incentives default to 0 | Full backward compatibility with existing integrations |
