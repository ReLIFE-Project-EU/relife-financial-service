# Risk Assessment API — Progress & To-Do

## Status: ✅ Implementation COMPLETE

---

## What the current implementation does

**Files:**
- `src/relife_financial/services/risk_assessment.py` — service layer
- `src/relife_financial/models/risk_assessment.py` — Pydantic request/response models
- `src/relife_financial/routes/risk_assessment.py` — FastAPI router
- `src/relife_financial/Indicator Modules/simulation_engine.py` — Monte Carlo engine

**Behaviour:**
- Supports a **single financing mode** per call: equity-only (`loan_amount=0`) or bank loan
- Accepts flat incentive overrides: `upfront_incentive_percentage`, `lifetime_incentive_amount`, `lifetime_incentive_years`
- Returns a single result object (one set of KPI percentiles/probabilities)
- `annual_energy_savings` is a fixed input — not stochastic
- Output detail controlled by `output_level` enum: `private`, `professional`, `public`, `complete`

---

## What the new logic adds

**Source file:** `Financial Service Updates/Risk Assessment/financial_simulation_with_schemes.py`
**Required inputs documentation:** `Financial Service Updates/Risk Assessment/inputs_required.md`

### 12 financing schemes (up from 2)

Grouped by shared cash-flow structure:

#### Family 1 — Debt-financed (client has upfront equity exposure)
`Year 0 = -(capex - proceeds)` | Annual = `savings·price - OM - debt_service`

| Scheme type | Key extra inputs |
|---|---|
| `equity` | none |
| `bank_loan` | `loan_amount`, `term_years` |
| `green_bond_loan` | `gb_proceeds`, `term_years`, `fixed_interest`, `OM_green` |
| `green_bond_bullet` | `gb_proceeds`, `term_years`, `fixed_interest`, `OM_green` |

→ **One unified function**, parameterised by `proceeds`, `repayment_type` (`none`/`amortising`/`bullet`), `OM_green`.

#### Family 2 — Zero-CAPEX client (provider covers upfront cost)
`Year 0 = 0` | Annual = `savings·price - OM - obligation_to_provider`

| Scheme type | Annual obligation | Key extra inputs |
|---|---|---|
| `on_bill` | fixed annuity via utility bill | `term_years`, `fixed_interest` |
| `operational_lease` | fixed lease payment | `lease_payment`, `term_years` |
| `epc_shared_savings` | `p_ESCO × savings` for N years | `p_ESCO`, `term_years` |
| `epc_first_out` | all savings until CAPEX recovered | none |
| `epc_guaranteed_savings` | amortising bank loan; ESCO compensates shortfall | `term_years`, `gs` (guaranteed savings amount) |

→ `on_bill` and `epc_guaranteed_savings` share a loan sub-helper. Others remain separate.

#### Family 3 — Crowdfunding (platform fee deducted at Year 0)
`Year 0 = crowd_capital - platform_fee - capex` | Annual = `savings·price - OM - payment_to_crowd`

| Scheme type | Annual crowd payment | Key extra inputs |
|---|---|---|
| `lending_crowdfunding` | fixed annuity (loan formula) | `loan_crowd`, `fixed_interest`, `term_years`, `fee_plat` |
| `royalty_crowdfunding` | `royalty_rate × revenue` for N years | `loan_crowd`, `royalty_rate`, `term_years`, `fee_plat` |
| `equity_crowdfunding` | `share_crowd × max(0, distributable_CF)` | `equity_crowd`, `share_crowd`, `fee_plat` |

→ **One unified function** parameterised by `payment_type`.

---

### New stochastic variable: energy savings

`annual_energy_savings` is now **stochastic** across Monte Carlo draws:
- Modelled as a Normal multiplicative factor (P50 = 1.0×, P10 = 0.70×)
- Each of the 10,000 draws samples a different savings realisation
- Captures real-world uncertainty that achieved savings differ from predicted savings

### Incentives system — removed

The current generic incentive parameters (`upfront_incentive_percentage`, `lifetime_incentive_amount`, `lifetime_incentive_years`) are **not present** in the new simulation logic. Incentive-like structures are absorbed into specific scheme types (ESCO, on-bill, etc.).

### Richer output

| Output field | Current | New |
|---|---|---|
| KPI percentile distributions | ✅ IRR, NPV, PBP, DPP, ROI | ✅ + `total_repayment` |
| Per-scheme results | ❌ single result | ✅ keyed by `scheme_type` |
| Year-by-year CF fan chart | ❌ | ✅ P5/P10/P25/P50/P75/P90/P95 bands for `cash_flows`, `inflows`, `outflows` |
| `Pr(NPV > 0)`, `Pr(PBP < T)` | ✅ | ✅ |

---

## Request model changes required

### Remove
- `loan_amount: Optional[float]`
- `loan_term: Optional[int]`
- `upfront_incentive_percentage: Optional[float]`
- `lifetime_incentive_amount: Optional[float]`
- `lifetime_incentive_years: Optional[int]`

### Add
```python
schemes: list[SchemeInput]  # one or more scheme types to evaluate
```

Where `SchemeInput` is a discriminated union (Pydantic) with one variant per scheme family, e.g.:

```python
class BankLoanDetails(BaseModel):
    loan_amount: float
    term_years: int

class SchemeInput(BaseModel):
    scheme_type: str          # e.g. "bank_loan", "equity", "epc_shared_savings"
    details: dict             # scheme-specific parameters
```

---

## Response model changes required

### Remove
Single flat result fields.

### Add
```python
results: dict[str, SchemeResult]   # keyed by scheme_type
```

Where `SchemeResult` contains:
```python
summary:
    percentiles: { IRR, NPV, PBP, DPP, ROI, total_repayment }
    probabilities: { Pr(NPV>0), Pr(PBP<T), Pr(DPP<T) }
    n_sims: int
kpi_histograms: { NPV, IRR, ROI, PBP, DPP }
cashflow_distributions:
    years: list[int]
    cash_flows: { P5, P10, P25, P50, P75, P90, P95 }
    inflows: { ... }
    outflows: { ... }
```

---

## Files to create / modify

| File | Action | Notes |
|---|---|---|
| `src/relife_financial/models/risk_assessment.py` | **Modify** | New `SchemeInput` models, updated `RiskAssessmentRequest`, new `SchemeResult` / `RiskAssessmentResponse` |
| `src/relife_financial/services/risk_assessment.py` | **Rewrite** | Replace `run_simulation` call with new scheme-dispatch logic; integrate all 3 cash-flow families |
| `src/relife_financial/routes/risk_assessment.py` | **Modify** | Update docstring, examples, error handling |
| `src/relife_financial/Indicator Modules/simulation_engine.py` | **Keep or deprecate** | New service will inline the simulation; old engine can remain for backward compat |

---

## To-Do (implementation order)

- [x] **Step 1 — Models**: Define `SchemeInput` discriminated types and updated request/response Pydantic models — ✅ `models/risk_assessment.py` replaced (12 scheme models, discriminated union, new `RiskAssessmentRequest` / `RiskAssessmentResponse`)
- [x] **Step 2 — Cash-flow functions**: Implement 12 cash-flow functions across 4 families — ✅ in `simulation_engine.py`
- [x] **Step 3 — Monte Carlo runner**: Port `get_kpi_results()` into `simulation_engine.py` with stochastic energy savings — ✅ `simulation_engine.py` replaced (42,863 bytes)
- [x] **Step 4 — Route + service update**: Service fully rewritten; route docstring, examples, and logging updated — ✅ `services/risk_assessment.py` + `routes/risk_assessment.py` updated
- [x] **Step 5 — Frontend changelog**: Breaking changes documented for frontend developer — ✅ `docs/RISK_ASSESSMENT_API_FRONTEND_CHANGELOG.md` created (request migration guide, all 12 scheme types with parameters, full response structure, migration checklist)
- [x] **Step 6 — Architecture doc**: `docs/API_ARCHITECTURE.md` Risk Assessment section updated — ✅ module chain, input model, Monte Carlo description, output structure, example requests, design decisions, and module origin table all updated
