# Risk Assessment API - Input Data Structure

This document clarifies which inputs are **user-provided** vs **dataset-provided** for the risk assessment endpoint.

## Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    API REQUEST                              │
│  (User provides some parameters, others come from dataset)  │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│               SERVICE LAYER LOGIC                           │
│  - Check if capex/opex provided by user                    │
│  - If None → fetch from internal dataset                   │
│  - Validate loan_amount ≤ capex (after dataset fetch)      │
│  - Load market forecasts (always from dataset)             │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              MONTE CARLO SIMULATION                         │
│  (All parameters now resolved, ready to compute)            │
└─────────────────────────────────────────────────────────────┘
```

---

## Input Parameters Classification

### 🔵 USER-PROVIDED INPUTS (Required)

These **must** be included in the API request:

| Parameter | Type | Validation | Description | Example |
|-----------|------|------------|-------------|---------|
| `annual_energy_savings` | `float` | `> 0` | Annual energy saved (kWh/year) | `27400` |
| `project_lifetime` | `int` | `1-30` | Project horizon (years) | `20` |

### 🟢 USER-PROVIDED INPUTS (Optional with Dataset Fallback)

These **can** be provided by user, but if `None`, will be fetched from internal dataset:

| Parameter | Type | Validation | Description | Example |
|-----------|------|------------|-------------|---------|
| `capex` | `Optional[float]` | `> 0` if provided | Capital expenditure (€) | `60000` |
| `annual_maintenance_cost` | `Optional[float]` | `≥ 0` if provided | Annual O&M cost (€/year) | `2000` |

**Default**: `None` → Service fetches from dataset

### 🟡 FINANCING INPUTS (User-Controlled, with Defaults)

User specifies loan details (defaults to all-equity if not provided):

| Parameter | Type | Validation | Description | Example |
|-----------|------|------------|-------------|---------|
| `loan_amount` | `float` | `≥ 0`, `≤ capex` | Loan principal (€) | `25000` |
| `loan_term` | `int` | `≥ 0`, `≤ project_lifetime` | Loan term (years) | `15` |

**Default**: `loan_amount=0`, `loan_term=0` (all-equity project)

**Validation**: 
- If `loan_amount > 0`, then `loan_term` must be `> 0`
- `loan_amount` cannot exceed `capex` (validated after dataset fetch if needed)

### 🟣 SIMULATION PARAMETERS (Optional)

| Parameter | Type | Validation | Description | Default |
|-----------|------|------------|-------------|---------|
| `n_sims` | `int` | `1000-100000` | Number of Monte Carlo runs | `10000` |
| `seed` | `int` | any integer | Random seed | `42` |

### 🔴 OUTPUT CONTROL

| Parameter | Type | Options | Description | Default |
|-----------|------|---------|-------------|---------|
| `output_level` | `str` | `minimal`, `standard`, `detailed`, `complete` | Response detail level | `standard` |
| `indicators` | `List[str]` | `["IRR", "NPV", "PBP", "DPP", "ROI"]` | Which indicators to compute | All 5 |
| `include_visualizations` | `Optional[bool]` | `True`, `False`, `None` | Override viz inclusion | `None` |

---

## Internal Dataset Inputs (NEVER User-Provided)

These are **always loaded from internal sources** (config files, database, or hard-coded):

### 📊 Market Forecast Data (30-Year Projections)

| Dataset | Scenarios | Description | Length | Unit |
|---------|-----------|-------------|--------|------|
| `inflation_rate_data` | P10/P50/P90 | Year-over-year inflation | 30 years | `% y/y` |
| `electricity_prices_data` | P10/P50/P90 | Grid electricity prices | 18 years | `€/kWh` |
| `interest_rate_data` | P10/P50/P90 | Loan interest rates | 16 years | `% y/y` |
| `discount_rate_data` | P10/P50/P90 | Discount rates for NPV/DPP | 1 scalar | fraction |

**Each dataset has 3 scenarios:**
- **Optimistic** = P90 (90th percentile)
- **Moderate** = P50 (median)
- **Pessimistic** = P10 (10th percentile)

These are used by `build_market_distributions()` to create year-specific distribution parameters.

---

## API Request Examples

### Example 1: User Provides Everything
```json
{
  "capex": 60000,
  "annual_maintenance_cost": 2000,
  "annual_energy_savings": 27400,
  "project_lifetime": 20,
  "loan_amount": 25000,
  "loan_term": 15,
  "output_level": "standard"
}
```

### Example 2: Dataset Provides CAPEX/OPEX
```json
{
  "annual_energy_savings": 27400,
  "project_lifetime": 20,
  "loan_amount": 25000,
  "loan_term": 15,
  "output_level": "detailed"
}
```
→ Service will fetch `capex` and `annual_maintenance_cost` from dataset

### Example 3: All-Equity Project (No Loan)
```json
{
  "capex": 50000,
  "annual_maintenance_cost": 1500,
  "annual_energy_savings": 20000,
  "project_lifetime": 15,
  "loan_amount": 0,
  "loan_term": 0,
  "output_level": "minimal"
}
```

---

## Service Layer Responsibilities

The `services/risk_assessment.py` file must:

1. **Check if user provided CAPEX/OPEX**
   ```python
   capex = request.capex if request.capex is not None else fetch_capex_from_dataset()
   opex = request.annual_maintenance_cost if request.annual_maintenance_cost is not None else fetch_opex_from_dataset()
   ```

2. **Validate loan_amount ≤ capex** (after resolving capex)
   ```python
   if request.loan_amount > capex:
       raise ValueError(f"loan_amount ({request.loan_amount}) cannot exceed capex ({capex})")
   ```

3. **Load market forecasts** (always from internal dataset)
   ```python
   market_data = load_market_forecasts()  # inflation, electricity, interest, discount rates
   ```

4. **Call simulation engine** with all resolved parameters
   ```python
   results = run_simulation(
       capex=capex,
       annual_maintenance_cost=opex,
       annual_energy_savings=request.annual_energy_savings,
       project_lifetime=request.project_lifetime,
       loan_amount=request.loan_amount,
       loan_term=request.loan_term,
       n_sims=request.n_sims,
       seed=request.seed,
       market_data=market_data
   )
   ```

---

## Summary Table

| Input Category | Source | Required | Fallback |
|----------------|--------|----------|----------|
| `annual_energy_savings` | User | ✅ Yes | None |
| `project_lifetime` | User | ✅ Yes | None |
| `capex` | User **or** Dataset | ❌ No | Dataset |
| `annual_maintenance_cost` | User **or** Dataset | ❌ No | Dataset |
| `loan_amount` | User | ❌ No | `0` (all-equity) |
| `loan_term` | User | ❌ No | `0` |
| `n_sims` | User | ❌ No | `10000` |
| `seed` | User | ❌ No | `42` |
| `output_level` | User | ❌ No | `standard` |
| Market Forecasts | **Internal Dataset** | N/A | Always loaded internally |

---

## Next Steps

1. ✅ **models/risk_assessment.py** - COMPLETED (defines Optional[float] for capex/opex)
2. ⏳ **services/risk_assessment.py** - TODO (implement fallback logic + dataset fetching)
3. ⏳ **routes/risk_assessment.py** - TODO (FastAPI endpoint)
4. ⏳ **Dataset integration** - TODO (decide how to store/retrieve CAPEX/OPEX values)

