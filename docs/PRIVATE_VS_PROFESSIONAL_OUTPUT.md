# Private vs Professional Output - Detailed Comparison

## Quick Reference Table

| Feature | Private (Homeowners) | Professional (Consultants) |
|---------|---------------------|---------------------------|
| **Target Audience** | Individual homeowners | Energy consultants, advisors |
| **Response Size** | ~8-12 KB | ~15-25 KB |
| **Focus** | Simple, actionable insights | Detailed risk analysis |
| **Point Forecasts** | ✅ P50 + 2 intuitive metrics | ✅ P50 only |
| **Percentiles** | ✅ P10-P90 for all indicators | ✅ P10-P90 for all indicators |
| **Probabilities** | ❌ Not included | ✅ 3 success metrics |
| **Visualizations** | Cash flow chart data | Distribution chart metadata |
| **Chart Support** | 1 chart (cash flow timeline) | 5 charts (indicator distributions) |

---

## Response Structure Comparison

### Private Output Structure

```json
{
  "point_forecasts": {
    // Core KPIs (P50 median)
    "NPV": 5432.10,
    "IRR": 5.7,
    "ROI": 15.2,
    "PBP": 8.3,
    "DPP": 10.1,
    
    // Additional intuitive metrics for homeowners
    "MonthlyAvgSavings": 345.64,   // Average monthly benefit
    "SuccessRate": 0.843           // Probability of profit
  },
  "percentiles": {
    // Full P10-P90 distributions for each indicator
    "NPV": {"P10": 2100, "P20": 3200, ..., "P90": 9800},
    "IRR": {"P10": 3.1, "P20": 4.0, ..., "P90": 8.9},
    "ROI": {"P10": ..., "P20": ..., ...},
    "PBP": {"P10": ..., "P20": ..., ...},
    "DPP": {"P10": ..., "P20": ..., ...}
  },
  "metadata": {
    "n_sims": 10000,
    "project_lifetime": 20,
    "capex": 60000,
    "annual_maintenance_cost": 2000,
    "annual_energy_savings": 27400,
    "loan_amount": 25000,
    "loan_term": 15,
    "annual_loan_payment": 1737.50,
    "loan_rate_percent": 3.5,
    
    // Cash flow data for timeline visualization
    "cash_flow_data": {
      "years": [0, 1, 2, ..., 20],
      "initial_investment": 35000,
      "annual_inflows": [0, 6740, 6960, ...],
      "annual_outflows": [35000, 1994, 2001, ...],
      "annual_net_cash_flow": [-35000, 4746, 4959, ...],
      "cumulative_cash_flow": [-35000, -30254, -25295, ...],
      "breakeven_year": 8,
      "loan_term": 15
    }
  }
}
```

### Professional Output Structure

```json
{
  "point_forecasts": {
    // Only core KPIs (P50 median) - NO intuitive metrics
    "NPV": 5432.10,
    "IRR": 5.7,
    "ROI": 15.2,
    "PBP": 8.3,
    "DPP": 10.1
  },
  "percentiles": {
    // Same P10-P90 distributions as private
    "NPV": {"P10": 2100, "P20": 3200, ..., "P90": 9800},
    "IRR": {"P10": 3.1, "P20": 4.0, ..., "P90": 8.9},
    "ROI": {"P10": ..., "P20": ..., ...},
    "PBP": {"P10": ..., "P20": ..., ...},
    "DPP": {"P10": ..., "P20": ..., ...}
  },
  "probabilities": {
    // NEW: Success probability metrics
    "Pr(NPV > 0)": 0.8435,
    "Pr(PBP < 20y)": 0.9124,
    "Pr(DPP < 20y)": 0.7563
  },
  "metadata": {
    "n_sims": 10000,
    "project_lifetime": 20,
    "capex": 60000,
    "annual_maintenance_cost": 2000,
    "annual_energy_savings": 27400,
    "loan_amount": 25000,
    "loan_term": 15,
    "discount_rate": 0.06,
    
    // NEW: Chart metadata for distribution graphs (NO cash flow data)
    "chart_metadata": {
      "NPV": {
        "bins": {
          "centers": [1200, 1450, 1700, ..., 12500],
          "counts": [45, 123, 289, ..., 67],
          "edges": [1075, 1325, 1575, ..., 12625]
        },
        "statistics": {
          "mean": 5500.0,
          "std": 2300.0,
          "P10": 2100.0,
          "P50": 5432.1,
          "P90": 9800.0
        },
        "chart_config": {
          "xlabel": "Net Present Value (€)",
          "ylabel": "Frequency (Number of Scenarios)",
          "title": "NPV Distribution (10,000 Simulations)"
        }
      },
      "IRR": { /* same structure */ },
      "ROI": { /* same structure */ },
      "PBP": { /* same structure */ },
      "DPP": { /* same structure */ }
    }
  }
}
```

---

## Field-by-Field Differences

### 1. `point_forecasts`

#### Private Output
```json
{
  "NPV": 5432.10,
  "IRR": 5.7,
  "ROI": 15.2,
  "PBP": 8.3,
  "DPP": 10.1,
  "MonthlyAvgSavings": 345.64,  // ← EXTRA: Simplified metric
  "SuccessRate": 0.843          // ← EXTRA: Simple probability
}
```

**Purpose**: 
- Includes 2 extra **intuitive metrics** that homeowners can easily understand
- `MonthlyAvgSavings`: "How much will I save per month on average?"
- `SuccessRate`: "What's the chance this investment makes money?"

#### Professional Output
```json
{
  "NPV": 5432.10,
  "IRR": 5.7,
  "ROI": 15.2,
  "PBP": 8.3,
  "DPP": 10.1
  // NO MonthlyAvgSavings
  // NO SuccessRate (moved to probabilities field)
}
```

**Purpose**: 
- Only standard financial indicators
- Professionals understand NPV/IRR without simplification
- Success probabilities provided separately with more detail

---

### 2. `percentiles`

#### Both Outputs (IDENTICAL)
```json
{
  "NPV": {"P10": 2100, "P20": 3200, ..., "P90": 9800},
  "IRR": {"P10": 3.1, "P20": 4.0, ..., "P90": 8.9},
  // ... etc
}
```

**Both include**:
- 9 percentiles (P10, P20, P30, P40, P50, P60, P70, P80, P90)
- All 5 indicators if requested
- Same calculation method

**Key point**: This field is **identical** in both outputs!

---

### 3. `probabilities`

#### Private Output
```json
// ❌ NOT INCLUDED
// (Simple SuccessRate is in point_forecasts instead)
```

#### Professional Output
```json
{
  "Pr(NPV > 0)": 0.8435,        // Probability of profitability
  "Pr(PBP < 20y)": 0.9124,      // Probability of payback within lifetime
  "Pr(DPP < 20y)": 0.7563       // Probability of discounted payback
}
```

**Why the difference?**
- **Private users** get simplified "SuccessRate" (just NPV > 0 probability) in `point_forecasts`
- **Professional users** get all 3 detailed probability metrics in separate field

---

### 4. `metadata` - Visualization Data

This is the **biggest difference** between outputs!

#### Private Output: `metadata.cash_flow_data`

```json
{
  "cash_flow_data": {
    "years": [0, 1, 2, ..., 20],
    "initial_investment": 35000,
    "annual_inflows": [0, 6740, 6960, 7190, ...],
    "annual_outflows": [35000, 1994, 2001, 2008, ...],
    "annual_net_cash_flow": [-35000, 4746, 4959, 5182, ...],
    "cumulative_cash_flow": [-35000, -30254, -25295, -20113, ...],
    "breakeven_year": 8,
    "loan_term": 15
  }
}
```

**Enables**: **1 chart** - Cash flow timeline showing:
- Year-by-year cash flows (inflows vs outflows)
- Cumulative position over time
- Break-even point visualization
- Intuitive "when will I get my money back?" view

**Chart type**: Line/area chart with time on X-axis

---

#### Professional Output: `metadata.chart_metadata`

```json
{
  "chart_metadata": {
    "NPV": {
      "bins": {
        "centers": [1200, 1450, 1700, ...],  // 30 bins
        "counts": [45, 123, 289, ...],
        "edges": [1075, 1325, 1575, ...]
      },
      "statistics": {
        "mean": 5500.0,
        "std": 2300.0,
        "P10": 2100.0,
        "P50": 5432.1,
        "P90": 9800.0
      },
      "chart_config": {
        "xlabel": "Net Present Value (€)",
        "ylabel": "Frequency (Number of Scenarios)",
        "title": "NPV Distribution (10,000 Simulations)"
      }
    },
    "IRR": { /* same structure */ },
    "ROI": { /* same structure */ },
    "PBP": { /* same structure */ },
    "DPP": { /* same structure */ }
  }
}
```

**Enables**: **5 charts** - Distribution histograms for each indicator:
- NPV distribution
- IRR distribution
- ROI distribution
- PBP distribution
- DPP distribution

Each shows:
- Histogram of 10,000 simulation outcomes
- P10/P50/P90 reference lines
- Mean and standard deviation
- Statistical uncertainty analysis

**Chart type**: Histogram with vertical lines for percentiles

---

## Visualization Comparison

### Private Output Visualization

**Single Chart: Cash Flow Timeline**

```
Cumulative Cash Flow Over Time
€
│
│         ┌────────────────
│       ┌─┘
│     ┌─┘
│   ┌─┘
│  ┌┘  Breakeven at Year 8
│ ┌┘
│┌┘
└────────────────────────── Years
0  5  10  15  20

Shows:
✓ When project breaks even
✓ Annual cash flows
✓ Long-term financial position
✓ Impact of loan payments
```

**User Question Answered**: "When will I see my money back?"

---

### Professional Output Visualizations

**Five Charts: Distribution Histograms**

```
NPV Distribution                 IRR Distribution
Frequency                        Frequency
│ ██                             │    ████
│████                            │  ████████
│██████                          │████████████
│████████                        │████████████
│██████████                      │████████████
│██████████                      │████████████
│  P10 P50 P90                   │  P10 P50 P90
└──────────────── NPV            └──────────────── IRR

(+ 3 more for ROI, PBP, DPP)

Shows:
✓ Range of possible outcomes
✓ Probability of different scenarios
✓ Risk/uncertainty visualization
✓ Statistical confidence intervals
```

**User Question Answered**: "What's the distribution of possible outcomes and associated risks?"

---

## Use Case Scenarios

### When to Use Private Output

**Target User**: Maria, a homeowner renovating her apartment

**Maria's Questions**:
1. "How much will I save per month?" → `MonthlyAvgSavings: 345.64`
2. "When will I break even?" → `cash_flow_data.breakeven_year: 8`
3. "What's the chance this makes sense?" → `SuccessRate: 0.843` (84.3%)
4. "Show me the timeline" → Cash flow chart from `cash_flow_data`

**Maria doesn't need**:
- Statistical distributions
- Detailed probability analysis
- Multiple risk scenarios

---

### When to Use Professional Output

**Target User**: Andreas, an energy consultant advising multiple clients

**Andreas's Questions**:
1. "What's the NPV distribution?" → `chart_metadata.NPV` histogram
2. "What's the risk profile?" → All 5 distribution charts
3. "What's the probability of payback?" → `probabilities` field (3 metrics)
4. "How volatile are the returns?" → `chart_metadata.*.statistics.std`
5. "Show P10-P90 range for client report" → `percentiles` field

**Andreas doesn't need**:
- Simplified "monthly savings" metric
- Single cash flow chart (uses percentiles to calculate himself)
- Homeowner-friendly summaries

---

## Response Size Comparison

### Private Output
```
Typical size: ~10 KB

Breakdown:
- point_forecasts: ~150 bytes (7 metrics)
- percentiles: ~1.5 KB (5 indicators × 9 percentiles)
- metadata.cash_flow_data: ~2 KB (arrays of 20 years)
- Other metadata: ~500 bytes
- Total: ~10-12 KB
```

### Professional Output
```
Typical size: ~20 KB (2x larger)

Breakdown:
- point_forecasts: ~100 bytes (5 metrics only)
- percentiles: ~1.5 KB (same as private)
- probabilities: ~100 bytes (3 metrics)
- metadata.chart_metadata: ~15 KB (5 indicators × 30 bins + statistics)
- Other metadata: ~500 bytes
- Total: ~18-25 KB

Why larger? Chart metadata contains histogram bins (30 bins × 5 indicators)
```

---

## Common Fields

Both outputs share these **identical fields**:

### `point_forecasts` (core indicators)
- NPV (median)
- IRR (median)
- ROI (median)
- PBP (median)
- DPP (median)

### `percentiles`
- Full P10-P90 distributions
- Same calculation method
- Same 9 percentiles
- All 5 indicators

### `metadata` (project parameters)
- `n_sims`: 10,000
- `project_lifetime`: e.g., 20 years
- `capex`: e.g., €60,000
- `annual_maintenance_cost`: e.g., €2,000
- `annual_energy_savings`: e.g., 27,400 kWh
- `loan_amount`: e.g., €25,000
- `loan_term`: e.g., 15 years
- `output_level`: "private" or "professional"
- `indicators_requested`: ["IRR", "NPV", ...]

---

## Key Differences Summary

| Aspect | Private | Professional |
|--------|---------|-------------|
| **Simplification** | Adds intuitive metrics | Pure technical metrics |
| **Probabilities** | Single "SuccessRate" in point_forecasts | 3 detailed metrics in separate field |
| **Visualization Focus** | Timeline (cash flow over years) | Risk analysis (outcome distributions) |
| **Number of Charts** | 1 (cash flow) | 5 (indicator distributions) |
| **Metadata Contains** | `cash_flow_data` | `chart_metadata` |
| **Target Question** | "When do I break even?" | "What's the risk profile?" |
| **Response Size** | ~10 KB | ~20 KB |
| **Technical Depth** | Low (homeowner-friendly) | High (consultant-level) |

---

## Migration Path

### Frontend Already Rendering Private Output?

**To add Professional Support**:

1. Check `output_level` in response
2. If `"professional"`:
   - Use `metadata.chart_metadata` instead of `metadata.cash_flow_data`
   - Render 5 histogram charts instead of 1 timeline chart
   - Display `probabilities` field prominently
   - Skip `MonthlyAvgSavings` and `SuccessRate` (not present)

3. If `"private"`:
   - Use existing `metadata.cash_flow_data` logic
   - Display `MonthlyAvgSavings` and `SuccessRate`
   - Skip `probabilities` field (not present)

---

## Example API Requests

### Request Private Output
```bash
curl -X POST /risk-assessment \
  -H "Content-Type: application/json" \
  -d '{
    "output_level": "private",
    "capex": 60000,
    "annual_energy_savings": 27400,
    ...
  }'
```

### Request Professional Output
```bash
curl -X POST /risk-assessment \
  -H "Content-Type: application/json" \
  -d '{
    "output_level": "professional",
    "capex": 60000,
    "annual_energy_savings": 27400,
    ...
  }'
```

**Same endpoint, different `output_level` parameter!**

---

## Frequently Asked Questions

### Q: Can I get both cash flow data AND chart metadata?

**A**: No, you must choose one `output_level`. However, you could:
- Make 2 API calls (one private, one professional)
- Use `output_level: "complete"` (includes both, but also base64 images = ~500 KB response)

### Q: Why doesn't professional output include cash flow data?

**A**: Professionals can calculate cash flows from the percentile distributions themselves. Including both would make the response too large (~30 KB).

### Q: Are the percentile distributions identical?

**A**: Yes! Both use the same Monte Carlo simulation results. The only difference is what visualization metadata is included.

### Q: Which output should I use for a web dashboard?

**A**: 
- **Homeowner dashboard** → Private (simpler, cash flow focus)
- **Consultant dashboard** → Professional (detailed risk analysis)
- **Flexible dashboard** → Check user role and switch dynamically

---

## Related Documentation

- [Cash Flow Chart Metadata](./CASH_FLOW_CHART_METADATA.md) - Private output visualization details
- [Professional Output Documentation](./PROFESSIONAL_OUTPUT_DOCUMENTATION.md) - Professional output usage guide
- [API User Inputs](./API_USER_INPUTS.md) - Complete endpoint specification

---

**Last Updated**: February 5, 2026  
**Version**: 1.0
