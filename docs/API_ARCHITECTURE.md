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
                    ├── Indicator Modules/simulation_engine.py
                    │       └── run_simulation()
                    │               ├── build_market_distributions()    ← derives Normal/Lognormal per-year distributions
                    │               ├── cash_flows()                    ← equity-only cash flow profile
                    │               ├── cash_flows_with_loan()          ← cash flow profile with debt service
                    │               ├── IRR()                           ← Internal Rate of Return
                    │               ├── NPV()                           ← Net Present Value
                    │               ├── PBP()                           ← Simple Payback Period
                    │               ├── DPP()                           ← Discounted Payback Period
                    │               └── ROI()                           ← Return on Investment
                    │
                    ├── Indicator Modules/indicator_outputs.py
                    │       ├── get_point_forecast()                    ← extracts P50 median value
                    │       ├── get_distribution_summary()              ← extracts percentile table
                    │       ├── get_full_distribution()                 ← returns raw 10 000-element array
                    │       └── get_success_probabilities()             ← Pr(NPV>0), Pr(PBP<N), Pr(DPP<N)
                    │
                    └── Indicator Modules/visualizations.py
                            ├── plot_indicator_distribution()           ← histogram per KPI
                            ├── generate_private_cash_flow_chart()      ← cash-flow waterfall for homeowners
                            └── generate_dashboard()                    ← combined multi-KPI overview
```

### Input Model — `RiskAssessmentRequest`

| Parameter | Type | Required | Description |
|---|---|---|---|
| `capex` | `float` \| `None` | Yes (currently) | Capital expenditure in € |
| `annual_energy_savings` | `float` | Yes | kWh/year saved (from energy API) |
| `annual_maintenance_cost` | `float` \| `None` | Yes (currently) | Annual O&M cost in € |
| `project_lifetime` | `int` (1–30) | Yes | Evaluation horizon in years |
| `loan_amount` | `float` | No (default 0) | Loan principal in € |
| `loan_term` | `int` | No (default 0) | Repayment period in years |
| `upfront_incentive_percentage` | `float` (0–100) | No (default 0) | CAPEX reduction at t=0 as % |
| `lifetime_incentive_amount` | `float` | No (default 0) | Annual OPEX reduction in €/year |
| `lifetime_incentive_years` | `int` | No (default 0) | Duration of OPEX reduction |
| `output_level` | `enum` | Yes | `private` / `professional` / `public` / `complete` |
| `indicators` | `list[str]` | No (default all) | Any subset of `["IRR","NPV","PBP","DPP","ROI"]` |
| `include_visualizations` | `bool` \| `None` | No | Override chart inclusion |

> **Note:** `output_level` is set by the *frontend tool*, not the end-user. It controls how much detail is returned.

### Monte Carlo Simulation — How It Works

`run_simulation()` (in `simulation_engine.py`) performs the following steps for each of 10,000 draws:

1. **Sample market variables** using `build_market_distributions()`, which converts three economic scenario paths (optimistic / moderate / pessimistic) into per-year probability distributions:
   - **Inflation rate** — Normal distribution; optimistic=low, pessimistic=high
   - **Electricity price** — Lognormal distribution (keeps prices positive); built-in data covering years 1–30
   - **Loan interest rate** — Normal distribution
   - **Discount rate** — Normal distribution
   
   The built-in economic scenario data is hardcoded in `run_simulation()` (calibrated to ECB 2% inflation target and current European market conditions).

2. **Generate cash flows** — depending on whether a loan is present:
   - `cash_flows()` for all-equity financing
   - `cash_flows_with_loan()` for partial/full debt financing
   
   Both functions apply incentives:
   - `upfront_incentive_percentage` reduces equity outflow at t=0
   - `lifetime_incentive_amount` reduces OPEX for the first `lifetime_incentive_years`

3. **Calculate KPIs** for each simulated scenario:
   - `IRR()` — discount rate that makes NPV = 0
   - `NPV()` — present value at a sampled discount rate
   - `PBP()` — years until undiscounted cumulative cash flows recover investment
   - `DPP()` — same as PBP but using discounted cash flows
   - `ROI()` — net profit / initial investment

4. **Return raw arrays** (10,000 values per KPI) + pre-computed summary statistics (percentiles, success probabilities)

### Output — `RiskAssessmentResponse`

The fields returned vary by `output_level`:

| Field | `private` | `professional` | `public` | `complete` |
|---|---|---|---|---|
| `point_forecasts` | ✅ P50 medians | ✅ P50 medians | ✅ P50 medians | ✅ P50 medians |
| `metadata` | ✅ simulation params + cash flow data | ✅ simulation params + chart metadata | ✅ simulation params | ✅ all |
| `percentiles` | ✅ P10–P90 per KPI | ✅ P10–P90 per KPI | ✅ P5–P95 per KPI | ✅ P5–P95 per KPI |
| `probabilities` | ❌ | ✅ Pr(NPV>0), Pr(PBP<N), Pr(DPP<N) | ✅ | ✅ |
| `visualizations` | ❌ (cash flow chart in metadata) | ❌ | ❌ | ✅ base64 PNG charts |

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

Predicts the **market value of a property after energy renovation** based on physical characteristics, location, and the post-renovation energy performance class (EPC label). The model has been trained on **Greek property market data**.

This API is designed to quantify the asset-value uplift from energy improvements and is expected to receive the post-renovation EPC label from a separate energy analysis API.

### Module Chain

```
routes/arv.py
    └── calculate_arv()
            │
            ▼
        services/arv.py
            └── predict_arv()
                    ├── _load_model()                ← lazy-loads data/lgb_model.pkl (LightGBM pipeline)
                    ├── _build_input_dataframe()     ← assembles single-row feature DataFrame
                    │       └── _map_property_type() ← translates English labels → Greek labels
                    └── model.predict()              ← returns predicted price per m²
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
| `energy_class` | `enum` | Yes | Post-renovation EPC label: `Η` (worst) → `Α+` (best) |
| `renovated_last_5_years` | `bool` | No (default `true`) | Whether recently renovated |

### EPC Classes (Greek Scale)

| Label | Level |
|---|---|
| `Η` | Worst |
| `Ζ` | — |
| `Ε` | — |
| `Δ` | — |
| `Γ` | — |
| `Β` | — |
| `Β+` | — |
| `Α` | — |
| `Α+` | Best |

### Model Details

- **Algorithm:** LightGBM (gradient-boosted decision trees)
- **Target:** Price per square meter (€/m²)
- **Input features:** `floor_area`, `building_age` (computed as `current_year − construction_year`), `floor_number`, `lat`, `lng`, `number_of_floors`, `energy_class`, `type` (Greek property category label), `renovated_last_5_years`
- **Training data:** Greek residential property market
- **File:** `src/relife_financial/data/lgb_model.pkl` (loaded once, singleton pattern)
- **Property type mapping:** English UI labels are mapped internally to Greek labels as used in the training data

### Output — `ARVResponse`

| Field | Type | Description |
|---|---|---|
| `price_per_sqm` | `float` | Predicted price per m² in € |
| `total_price` | `float` | `price_per_sqm × floor_area` |
| `floor_area` | `float` | Echo of input floor area |
| `energy_class` | `string` | Echo of input energy class |
| `metadata` | `dict` | Model version, prediction timestamp, etc. |

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
| `simulation_engine.py` | Core Monte Carlo engine: cash-flow generation, KPI calculation, market distribution sampling |
| `indicator_outputs.py` | Utility functions for extracting and formatting KPI results (point forecasts, percentile tables, probability estimates, raw distributions) |
| `visualizations.py` | Chart generation: per-indicator distribution histograms, private cash-flow chart, and multi-KPI dashboard |

---

## Example Requests

### Risk Assessment — Private User (Homeowner)

```json
POST /risk-assessment
{
    "capex": 60000,
    "annual_energy_savings": 27400,
    "annual_maintenance_cost": 2000,
    "project_lifetime": 20,
    "loan_amount": 20000,
    "loan_term": 15,
    "upfront_incentive_percentage": 10.0,
    "lifetime_incentive_amount": 500.0,
    "lifetime_incentive_years": 5,
    "output_level": "private",
    "indicators": ["NPV", "PBP", "ROI", "IRR"]
}
```

### Risk Assessment — Professional (Energy Consultant)

```json
POST /risk-assessment
{
    "capex": 60000,
    "annual_energy_savings": 27400,
    "annual_maintenance_cost": 2000,
    "project_lifetime": 20,
    "output_level": "professional",
    "indicators": ["IRR", "NPV", "PBP", "DPP", "ROI"]
}
```

### After Renovation Value

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
    "energy_class": "Β+",
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
| `capex` and `annual_maintenance_cost` optional (None) | Planned future feature: auto-lookup from internal dataset; currently required |
| LightGBM singleton loaded lazily | Avoids loading the model on every request; keeps startup fast |
| English → Greek property type mapping in ARV service | Decouples the API contract from the model's training data vocabulary |
| Incentives default to 0 | Full backward compatibility with existing integrations |
