# Risk Assessment API — Frontend Integration & Migration Guide

## What Changed

The Risk Assessment endpoint (`POST /risk-assessment`) has been significantly updated to support **12 financing schemes across 4 scheme families**, all evaluated in a single API call. The flat single-scheme request model has been replaced with a `schemes` array pattern, and the response now returns per-scheme results keyed by `scheme_type`.

---

## Breaking Changes Summary

| # | What | Before | After |
|---|------|--------|-------|
| 1 | Request field removed | `loan_amount: float` | **Removed** |
| 2 | Request field removed | `loan_term: int` | **Removed** |
| 3 | Request field removed | `upfront_incentive_percentage: float` | **Removed** |
| 4 | Request field removed | `lifetime_incentive_amount: float` | **Removed** |
| 5 | Request field removed | `lifetime_incentive_years: int` | **Removed** |
| 6 | Request field added | — | `schemes: list[SchemeInput]` **(required)** |
| 7 | Response top-level field removed | `point_forecasts` | **Removed** — now `results[scheme_type].summary.percentiles.*P50` |
| 8 | Response top-level field removed | `percentiles` | **Removed** — now `results[scheme_type].summary.percentiles` |
| 9 | Response top-level field removed | `probabilities` | **Removed** — now `results[scheme_type].summary.probabilities` |
| 10 | Response top-level field removed | `visualizations` | **Removed** — render charts client-side from `cashflow_distributions` / `kpi_histograms` |
| 11 | Response structure | flat single-scheme result | nested `results: { [scheme_type]: SchemeResult }` |

---

## Request

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `capex` | `float` | — | Total investment cost (€). **Now optional** — omit to have it computed from `country` + `renovation_actions`. |
| `annual_energy_savings` | `float` | ✅ | Expected annual energy savings (kWh/year) |
| `annual_maintenance_cost` | `float` | — | Annual O&M cost (€/year). **Now optional** — omit to have it computed from `country` + `renovation_actions`. Defaults to `0` when only insulation/windows are present. |
| `project_lifetime` | `int` (1–30) | ✅ | Evaluation horizon (years) |
| `schemes` | `list[SchemeInput]` | ✅ | One or more financing schemes to evaluate (see below). Minimum 1, maximum 12 |
| `output_level` | `enum` | ✅ | `private` / `professional` / `public` / `complete` |
| `indicators` | `list[str]` | — | KPIs to return. Default: all. Any subset of `["IRR","NPV","PBP","DPP","ROI"]` |
| `country` | `string` | (see note) | EU country name. **Required when `capex` or `annual_maintenance_cost` is omitted.** See supported values below. |
| `renovation_actions` | `list[RenovationAction]` | (see note) | Renovation package for price lookup. **Required when `capex` or `annual_maintenance_cost` is omitted.** See schema below. |

> **Lookup rule:** if either `capex` or `annual_maintenance_cost` is absent, both `country` and `renovation_actions` must be provided. You may supply one of the two financial fields explicitly and let the other be computed — the fields are independent.

> **Note:** `output_level` is set by the *frontend tool* based on the user's context (homeowner vs. energy consultant), not entered directly by the end-user.

---

### CAPEX / OPEX automatic lookup

When `capex` and/or `annual_maintenance_cost` are omitted the API resolves them from built-in EU reference data (source: Danish Energy Agency / Eurostat, 2024–2025).

#### `RenovationAction` object

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `action` | `string` | ✅ | Renovation work type — must be one of the 10 canonical names below |
| `area_m2` | `float > 0` | (see note) | Surface area in m² — **required for insulation and windows actions** |
| `capacity_kw` | `float > 0` | (see note) | Installed system capacity in kW — **required for HVAC, PV, and solar actions** |
| `material` | `string` | — | Optional material variant (e.g. `EPS`, `MW`, `GW` for wall insulation; `PVC`, `Al`, `Wood` for windows). If omitted, the average price across available material variants is used. |

#### Supported renovation actions

| Action name | Price unit | Required field |
|---|---|---|
| `Wall insulation` | €/m² | `area_m2` |
| `Wall insulation - additional` | €/m² | `area_m2` |
| `Roof insulation - Accessible` | €/m² | `area_m2` |
| `Roof insulation - Makeover` | €/m² | `area_m2` |
| `Floor insulation` | €/m² | `area_m2` |
| `Windows` | €/m² | `area_m2` |
| `Air-water Heat Pump` | €/kW + fixed € | `capacity_kw` |
| `Condensing boiler` | €/kW + fixed € | `capacity_kw` |
| `PV` | €/kW | `capacity_kw` |
| `Solar thermal panels` | €/kW + fixed € | `capacity_kw` |

> **OPEX note:** insulation and windows have no annual maintenance cost in the reference data — they contribute €0/year to `annual_maintenance_cost`. HVAC, PV, and solar thermal each carry a flat country-specific annual O&M cost (€/year, not scaled by capacity).

#### Supported countries (27 EU member states)

`Austria`, `Belgium`, `Bulgaria`, `Croatia`, `Cyprus`, `Czech Republic`, `Denmark`, `Estonia`, `Finland`, `France`, `Germany`, `Greece`, `Hungary`, `Ireland`, `Italy`, `Latvia`, `Lithuania`, `Luxembourg`, `Malta`, `Netherlands`, `Poland`, `Portugal`, `Romania`, `Slovakia`, `Slovenia`, `Spain`, `Sweden`

> Both `"Czech Republic"` and `"Czechia"` are accepted. Country names are case-insensitive.

---

### `schemes` array — scheme types and parameters

Each object in `schemes` must contain `scheme_type` (the discriminator) plus any scheme-specific parameters listed below.

#### Family 1 — Self-financed (client pays full CAPEX upfront)

| `scheme_type` | Extra fields | Description |
|---|---|---|
| `equity` | *(none)* | 100% owner equity, no external financing |

#### Family 2 — Debt-financed (client takes partial or full loan)

| `scheme_type` | Extra fields | Notes |
|---|---|---|
| `bank_loan` | `loan_amount: float`, `term_years: int` | Standard amortising bank loan at market rate |
| `green_bond_loan` | `gb_proceeds: float`, `term_years: int`, `fixed_interest: float`, `OM_green: float` | Green bond, amortising repayment schedule |
| `green_bond_bullet` | `gb_proceeds: float`, `term_years: int`, `fixed_interest: float`, `OM_green: float` | Green bond, full principal repaid at maturity |

#### Family 3 — Zero-CAPEX for client (provider covers upfront cost)

| `scheme_type` | Extra fields | Notes |
|---|---|---|
| `on_bill` | `term_years: int`, `fixed_interest: float` | Financed by utility; repaid through energy bills |
| `operational_lease` | `lease_payment: float`, `term_years: int` | Fixed lease instalments paid to lessor |
| `epc_shared_savings` | `p_ESCO: float`, `term_years: int` | ESCO takes a fraction of realised savings for N years |
| `epc_first_out` | *(none)* | ESCO takes all savings until full CAPEX is recovered |
| `epc_guaranteed_savings` | `term_years: int`, `gs: float` | ESCO guarantees a minimum savings level (€/year in today's money); shortfall covered by ESCO |

#### Family 4 — Crowdfunding (platform fee deducted at Year 0)

| `scheme_type` | Extra fields | Notes |
|---|---|---|
| `lending_crowdfunding` | `loan_crowd: float`, `fixed_interest: float`, `term_years: int`, `fee_plat: float` | Loan from crowd investors, amortising fixed repayment |
| `royalty_crowdfunding` | `loan_crowd: float`, `royalty_rate: float`, `term_years: int`, `fee_plat: float` | Revenue-share royalty paid to crowd investors for N years |
| `equity_crowdfunding` | `equity_crowd: float`, `share_crowd: float`, `fee_plat: float` | Crowd investors hold an equity stake in savings proceeds |

**Rate / fraction fields:** `fixed_interest`, `p_ESCO`, `royalty_rate`, `share_crowd`, `fee_plat` are all **fractions** (e.g. `0.035` for 3.5%). Do **not** pass percentage values.

---

## Example Requests

### Homeowner — equity only, minimal output

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
    "indicators": ["NPV", "PBP", "IRR"]
}
```

### Energy consultant — compare 3 schemes side by side

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
    "indicators": ["NPV", "IRR", "PBP", "ROI"]
}
```

### Homeowner — CAPEX and OPEX computed from renovation package

```json
POST /risk-assessment
{
    "annual_energy_savings": 27400,
    "project_lifetime": 20,
    "output_level": "private",
    "country": "Italy",
    "renovation_actions": [
        { "action": "Wall insulation",    "area_m2": 120 },
        { "action": "Roof insulation - Accessible", "area_m2": 80 },
        { "action": "Air-water Heat Pump", "capacity_kw": 8 }
    ],
    "schemes": [
        { "scheme_type": "equity" }
    ],
    "indicators": ["NPV", "PBP", "IRR"]
}
```

> The API will look up Italian unit prices for each action, sum them into `capex`, and compute the annual heat-pump O&M cost as `annual_maintenance_cost`. Both resolved values are echoed back in `metadata` along with `capex_from_lookup: true` and `opex_from_lookup: true`.

### Homeowner — explicit CAPEX, O&M computed from renovation package

```json
POST /risk-assessment
{
    "capex": 35000,
    "annual_energy_savings": 22000,
    "project_lifetime": 20,
    "output_level": "private",
    "country": "Germany",
    "renovation_actions": [
        { "action": "PV", "capacity_kw": 6 }
    ],
    "schemes": [
        { "scheme_type": "equity" },
        { "scheme_type": "bank_loan", "loan_amount": 20000, "term_years": 10 }
    ]
}
```

> `capex` is provided explicitly; only `annual_maintenance_cost` is resolved from the lookup.

---

### ESCO comparison — all three contract variants

```json
POST /risk-assessment
{
    "capex": 80000,
    "annual_energy_savings": 35000,
    "annual_maintenance_cost": 1500,
    "project_lifetime": 25,
    "output_level": "complete",
    "schemes": [
        {"scheme_type": "epc_first_out"},
        {"scheme_type": "epc_guaranteed_savings", "term_years": 15, "gs": 8000},
        {"scheme_type": "epc_shared_savings", "p_ESCO": 0.40, "term_years": 12}
    ]
}
```

### Migrating an old bank-loan request

Old request:
```json
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

New equivalent (incentive fields have no direct equivalent — omit or encode in CAPEX):
```json
{
    "capex": 54000,
    "annual_energy_savings": 27400,
    "annual_maintenance_cost": 2000,
    "project_lifetime": 20,
    "output_level": "private",
    "schemes": [
        {"scheme_type": "bank_loan", "loan_amount": 20000, "term_years": 15}
    ],
    "indicators": ["NPV", "PBP", "ROI", "IRR"]
}
```

> ℹ️ The old `upfront_incentive_percentage` reduced CAPEX at Year 0. If needed, apply the reduction to `capex` directly before sending. The `lifetime_incentive_*` fields had no direct mapping in the new model — consult the project team if this scenario is required.

---

## Response

### Top-level structure

```json
{
    "results": {
        "<scheme_type>": SchemeResult,
        ...
    },
    "metadata": { ... }
}
```

`results` contains one key per scheme requested. The key is the same `scheme_type` string sent in the request.

---

### `SchemeResult` fields

| Field | Present when | Description |
|-------|-------------|-------------|
| `scheme_id` | Always | Integer 1–12 identifying the scheme type |
| `scheme_family` | Always | One of: `self_financed`, `debt_financed`, `esco_zero_capex`, `crowdfunding` |
| `summary.percentiles` | Always | P5/P10/P50/P90/P95 per requested KPI (see note on `indicators`) |
| `summary.probabilities` | Always | `Pr(NPV > 0)`, `Pr(PBP < Ty)`, `Pr(DPP < Ty)` |
| `summary.disc_target_used` | Always | Discount rate used for NPV/DPP (P50 Monte Carlo draw) |
| `summary.n_sims` | Always | Number of Monte Carlo draws — always `10000` |
| `cashflow_distributions` | Always | Year-by-year fan chart data for cash flows, inflows, and outflows |
| `kpi_histograms` | `professional`, `public`, `complete` | Histogram bin data for NPV, IRR, ROI, PBP, DPP |

> **Note on `indicators`:** `summary.percentiles` is filtered to the KPIs listed in `indicators`. `total_repayment` (relevant for debt schemes) is always included when applicable, even if not in `indicators`.

---

### `cashflow_distributions` structure

```json
{
    "years": [0, 1, 2, ..., 20],
    "cash_flows": {
        "P5":  [-60000, 800,  ...],
        "P10": [-60000, 1100, ...],
        "P50": [-60000, 2100, ...],
        "P90": [-60000, 3200, ...],
        "P95": [-60000, 3600, ...]
    },
    "inflows":  { "P5": [...], "P10": [...], "P50": [...], "P90": [...], "P95": [...] },
    "outflows": { "P5": [...], "P10": [...], "P50": [...], "P90": [...], "P95": [...] }
}
```

- `years[0]` is Year 0 (the investment year). All arrays have length `project_lifetime + 1`.
- `P5`/`P95` are the extreme percentile bands; `P50` is the median scenario.
- Use `cash_flows` for net cash flow fan charts, `inflows`/`outflows` for stacked bar decomposition.

---

### `kpi_histograms` structure (professional / public / complete only)

```json
{
    "NPV": {
        "bin_edges":         [-75000, -69000, -63000, ...],  // 31 values — edges of 30 bins
        "feasible_counts":   [0, 0, 3, 12, 45, ...],        // 30 values — scenarios where NPV ≥ 0
        "infeasible_counts": [4, 5, 12, 20, 30, ...],       // 30 values — scenarios where NPV < 0
        "p10": -26812.5,
        "p50": -978.3,
        "p90": 27170.3,
        "project_lifetime": null   // null for NPV / IRR / ROI
    },
    "PBP": {
        "bin_edges":         [5.1, 7.9, 10.8, ...],
        "feasible_counts":   [995, 3843, 2694, ...],        // paid back within project_lifetime
        "infeasible_counts": [0, 0, 0, ...],                // did NOT pay back
        "p10": 7.9,
        "p50": 10.9,
        "p90": 17.3,
        "project_lifetime": 20   // threshold used to split feasible/infeasible
    }
    // IRR, ROI, DPP: same structure
}
```

**Rendering:** bin `i` spans `bin_edges[i]` to `bin_edges[i+1]`. Stack `feasible_counts[i]` (positive colour) and `infeasible_counts[i]` (warning colour). Mark `p50` with a vertical line.

> ⚠️ For DPP/PBP: `sum(feasible) + sum(infeasible)` may be less than 10,000 — scenarios where the project never pays back under discounting are excluded from the histogram.

---

### `metadata` fields

| Field | Type | Description |
|-------|------|-------------|
| `capex` | float | CAPEX value used in the simulation (either the supplied value or the lookup result) |
| `capex_from_lookup` | bool | `true` if `capex` was resolved from the reference data; `false` if supplied explicitly |
| `annual_energy_savings` | float | Echo of input energy savings |
| `annual_maintenance_cost` | float | Annual O&M cost used in the simulation (either supplied or lookup result) |
| `opex_from_lookup` | bool | `true` if `annual_maintenance_cost` was resolved from the reference data; `false` if supplied explicitly |
| `project_lifetime` | int | Echo of project lifetime |
| `n_schemes` | int | Number of schemes evaluated |
| `scheme_types` | list[str] | List of evaluated `scheme_type` keys (same order as `results`) |
| `output_level` | str | `output_level` used |
| `indicators_requested` | list[str] | `indicators` value used |
| `n_sims` | int | Always `10000` |

---

### `output_level` reference

| Data | `private` | `professional` | `public` | `complete` |
|---|:---:|:---:|:---:|:---:|
| `summary` (percentiles + probabilities) | ✅ | ✅ | ✅ | ✅ |
| `cashflow_distributions` | ✅ | ✅ | ✅ | ✅ |
| `kpi_histograms` | ❌ | ✅ | ✅ | ✅ |

---

## Example Response

Request: `schemes: [{"scheme_type": "equity"}]`, `output_level: "professional"`, `project_lifetime: 20`, `indicators: ["NPV","IRR","PBP"]`

```json
{
    "results": {
        "equity": {
            "scheme_id": 1,
            "scheme_family": "self_financed",
            "summary": {
                "percentiles": {
                    "NPV": {"P5": -8200, "P10": -4100, "P50": 15400, "P90": 38200, "P95": 44500},
                    "IRR": {"P5": 0.031, "P10": 0.045, "P50": 0.084, "P90": 0.134, "P95": 0.148},
                    "PBP": {"P5": 8.1,   "P10": 9.2,   "P50": 11.4,  "P90": 14.9,  "P95": 16.2}
                },
                "probabilities": {
                    "Pr(NPV > 0)":   0.912,
                    "Pr(PBP < Ty)":  0.956,
                    "Pr(DPP < Ty)":  0.878
                },
                "disc_target_used": 0.05,
                "n_sims": 10000
            },
            "kpi_histograms": {
                "NPV": {"bin_edges": [-15000, -10000, -5000, 0, 5000, 10000, 15000, 20000, 25000, 30000, 35000],
                        "feasible_counts":   [0, 0, 0, 0, 680, 890, 1100, 1240, 1380, 900],
                        "infeasible_counts": [85, 120, 280, 420, 0, 0, 0, 0, 0, 0],
                        "p10": -4100, "p50": 15400, "p90": 38200, "project_lifetime": null},
                "IRR": {"bin_edges": [0.0, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.10],
                        "feasible_counts":   [0, 0, 0, 420, 850, 1400, 1820, 1900, 1600, 980],
                        "infeasible_counts": [12, 45, 180, 0, 0, 0, 0, 0, 0, 0],
                        "p10": 0.045, "p50": 0.084, "p90": 0.134, "project_lifetime": null}
            },
            "cashflow_distributions": {
                "years": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20],
                "cash_flows": {
                    "P50": [-60000, 1850, 1920, 1990, 2060, 2135, 2210, 2290, 2370, 2455, 2545,
                             2635,  2730, 2825, 2920, 3025, 3130, 3240, 3350, 3465, 3585]
                },
                "inflows":  {"P50": [0, 5050, 5180, 5310, 5445, 5585, 5725, 5870, 6020, 6170, 6325,
                                      6490, 6655, 6825, 7000, 7180, 7365, 7555, 7750, 7950, 8155]},
                "outflows": {"P50": [-60000, -3200, -3260, -3320, -3385, -3450, -3515, -3580,
                                     -3650, -3715, -3780, -3855, -3925, -4000, -4080, -4155,
                                     -4235, -4315, -4400, -4485, -4570]}
            }
        }
    },
    "metadata": {
        "capex": 60000,
        "annual_energy_savings": 27400,
        "annual_maintenance_cost": 2000,
        "project_lifetime": 20,
        "n_schemes": 1,
        "scheme_types": ["equity"],
        "output_level": "professional",
        "indicators_requested": ["NPV", "IRR", "PBP"],
        "n_sims": 10000
    }
}
```

---

## Visualization Guide

### Important: charts moved from backend to frontend

The old API generated a cash flow chart server-side and returned it as a base64 PNG inside `metadata.visualizations`. **This is gone.** The API now returns the raw numerical data; the frontend is responsible for all chart rendering. This enables richer, interactive charts and removes the bandwidth cost of embedded images.

---

### Design philosophy per output level

| Level | Audience | Design goal |
|---|---|---|
| `private` | Homeowner / property owner | **Simple and reassuring.** One clean number per KPI, one easy-to-read chart. Avoid jargon. Show what they get, not how uncertain it is. |
| `professional` | Energy consultant, financial advisor | **Rich and statistically complete.** Uncertainty bands, probability metrics, full distributions. Enable scheme comparison. |
| `public` | General public / portal users | Same data richness as `professional`, but with clearer labels and less assumption of financial literacy. |
| `complete` | API power users, researchers | All of the above. |

---

### `private` — recommended charts

**Goal:** one scheme, one clear story, no uncertainty jargon.

#### 1. Annual net cash flow bar chart (core chart — replaces the old backend-generated PNG)

- **Data:** `results[schemeType].cashflow_distributions.cash_flows.P50`
- Plot one vertical bar per year (index 0 = Year 0, the investment year)
- Year 0 bar: negative (investment outlay) — use a distinct colour (e.g. red/orange)
- Years 1–N bars: positive net benefit — use a positive colour (e.g. green/teal)
- Overlay a cumulative sum line to show where the investment is recovered
- **Mark the payback year** with a vertical dashed line and label: "Paid back in year X"
- Do **not** show uncertainty bands — P50 only

```
Data fields used:
  cashflow_distributions.years           → x-axis
  cashflow_distributions.cash_flows.P50  → bar heights
  summary.percentiles.PBP.P50            → payback marker position
```

#### 2. Summary card (headline numbers)

Show only **P50 median** values, with plain-language labels:

| API field | Plain label |
|---|---|
| `summary.percentiles.NPV.P50` | "Expected total gain over X years" (€) |
| `summary.percentiles.IRR.P50` | "Equivalent annual return" (%) |
| `summary.percentiles.PBP.P50` | "Expected payback period" (years) |
| `summary.percentiles.ROI.P50` | "Total return on investment" (%) |

Do **not** show probabilities (`Pr(NPV > 0)` etc.) — these require statistical literacy and can alarm users if misread.

#### Multiple schemes in `private` mode

If multiple schemes are present, show a simple **scheme comparison card grid** — one card per scheme with its P50 summary numbers. Do not overlay schemes on a single chart.

---

### `professional` / `public` — recommended charts

**Goal:** full statistical picture, scheme comparison, uncertainty quantified.

#### 1. Cash flow fan chart

- **Data:** `cashflow_distributions.cash_flows` — all percentile bands
- Plot shaded bands:  outer band = P5–P95 (lightest shade), inner band = P10–P90, centre line = P50 (solid)
- Optionally decompose into `inflows` vs `outflows` as a stacked area chart to show what drives the uncertainty
- Include a cumulative sum overlay (from `cash_flows.P50`) to show expected payback trajectory

```
Data fields used:
  cashflow_distributions.years
  cashflow_distributions.cash_flows.{P5, P10, P50, P90, P95}
  cashflow_distributions.inflows.P50   (optional decomposition)
  cashflow_distributions.outflows.P50  (optional decomposition)
```

#### 2. KPI distribution histograms (from `kpi_histograms`)

Render at minimum **NPV** and **IRR** histograms. Optionally also ROI and PBP.

- Each histogram: bin `i` spans `bin_edges[i]` to `bin_edges[i+1]`; stack `feasible_counts[i]` (positive colour) on top of `infeasible_counts[i]` (warning colour)
- Mark the P50 value with a vertical line using the embedded `kpi_histograms.NPV.p50` (no need to cross-reference `summary.percentiles`)
- Annotate PBP/DPP histograms with a "Project lifetime" threshold line at `kpi_histograms.PBP.project_lifetime`
- Add an annotation: "X% of scenarios profitable" from `summary.probabilities["Pr(NPV > 0)"]`

```
Data fields used:
  kpi_histograms.NPV.bin_edges                    → bin ranges (bin i spans edge[i] to edge[i+1])
  kpi_histograms.NPV.feasible_counts              → bar heights, positive colour
  kpi_histograms.NPV.infeasible_counts            → stacked bar, warning colour (NPV < 0)
  kpi_histograms.NPV.p50                          → median marker line
  kpi_histograms.IRR.bin_edges / feasible_counts  → same pattern
  summary.probabilities["Pr(NPV > 0)"]            → annotation text
```

#### 3. Probability / risk summary bar

Display `summary.probabilities` as a visual indicator (progress bar, gauge, or badge).

> **Key format:** probability keys embed the actual project lifetime, e.g. for a 20-year project: `"Pr(PBP < 20y)"`. Always use `metadata.project_lifetime` to build the key dynamically: `` `Pr(PBP < ${metadata.project_lifetime}y)` ``

| Key pattern | Label |
|---|---|
| `"Pr(NPV > 0)"` | "Probability investment is profitable" |
| `` `Pr(PBP < ${lifetime}y)` `` | "Probability fully paid back within project lifetime" |
| `` `Pr(DPP < ${lifetime}y)` `` | "Probability discounted payback within project lifetime" |

#### 4. KPI percentile table

Show P10 / P50 / P90 for each requested KPI in a table. Label P10 as "pessimistic", P50 as "expected", P90 as "optimistic".

#### Multiple schemes in `professional` / `public` mode

When `n_schemes > 1`, add a **scheme comparison chart**:

- Grouped bar chart: one group per KPI (NPV, IRR), one bar per scheme — bar height = P50 value
- Or a scatter plot: x = IRR P50, y = NPV P50, one point per scheme — lets the user see risk/return trade-offs at a glance
- Show scheme family as colour coding (`self_financed`, `debt_financed`, `esco_zero_capex`, `crowdfunding`)

```
Data fields used (per scheme):
  scheme_family           → colour coding
  summary.percentiles.NPV.{P10, P50, P90}
  summary.percentiles.IRR.{P10, P50, P90}
  summary.probabilities["Pr(NPV > 0)"]
```

---

### `complete` — same as `professional` with full bands

Use P5–P95 bands everywhere (available in `cashflow_distributions` and `summary.percentiles` for all levels). The `complete` level adds no additional API fields — it is intended for research use where the full distribution width matters.

---

### Chart data availability summary

| Chart | `private` | `professional` | `public` | `complete` |
|---|:---:|:---:|:---:|:---:|
| Cash flow bar chart (P50 only) | ✅ | — | — | — |
| Cash flow fan chart (P5–P95) | — | ✅ | ✅ | ✅ |
| KPI histograms | ❌ no data | ✅ | ✅ | ✅ |
| Probability gauges | ✅ data available | ✅ | ✅ | ✅ |
| Percentile table | P50 only | P10–P90 | P10–P90 | P5–P95 |
| Scheme comparison chart | card grid | full chart | full chart | full chart |

> ℹ️ Probability data (`summary.probabilities`) is returned for **all** output levels including `private`. For `private`, use it only to power a simple plain-language statement ("Your investment is expected to pay back in X years in 9 out of 10 scenarios"), not as a raw statistic.

---

## Migration Checklist

- [ ] Remove `loan_amount` from the request payload
- [ ] Remove `loan_term` from the request payload
- [ ] Remove `upfront_incentive_percentage`, `lifetime_incentive_amount`, `lifetime_incentive_years` from the request payload
- [ ] Add `schemes` array to the request — minimum one entry with `scheme_type`
- [ ] Map previously used `loan_amount` / `loan_term` to `{"scheme_type": "bank_loan", "loan_amount": ..., "term_years": ...}`
- [ ] Update response parsing: flat `point_forecasts.NPV` → `results[schemeType].summary.percentiles.NPV.P50`
- [ ] Update response parsing: flat `percentiles.IRR` → `results[schemeType].summary.percentiles.IRR` (full P5–P95 object)
- [ ] Update response parsing: flat `probabilities` → `results[schemeType].summary.probabilities`
- [ ] *(New — optional)* To use automatic CAPEX/OPEX lookup: remove `capex` and/or `annual_maintenance_cost` from the request; add `country` (string) and `renovation_actions` (array) instead
- [ ] *(New)* Read `metadata.capex_from_lookup` and `metadata.opex_from_lookup` to know which values were resolved automatically — display them to the user if relevant (e.g. "Estimated installation cost: €24,387")
- [ ] *(New — optional)* To use automatic CAPEX/OPEX lookup: remove `capex` and/or `annual_maintenance_cost` from the request; add `country` (string) and `renovation_actions` (array) instead
- [ ] *(New)* Read `metadata.capex_from_lookup` and `metadata.opex_from_lookup` to know which values were resolved automatically — display them to the user if relevant (e.g. "Estimated installation cost: €24,387")
- [ ] Remove `visualizations` response handling — the field no longer exists. The old backend-generated cash flow PNG is replaced by `cashflow_distributions` (raw per-year data) and `kpi_histograms` (histogram bin data). Implement charts client-side following the Visualization Guide above
- [ ] When multiple schemes are requested, iterate `Object.keys(results)` to display each scheme result
- [ ] Verify all rate inputs (`fixed_interest`, `p_ESCO`, `royalty_rate`, `share_crowd`, `fee_plat`) are sent as fractions (0.035), not percentages (3.5)
