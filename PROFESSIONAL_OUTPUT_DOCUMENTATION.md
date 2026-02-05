# Professional Output Level - Risk Assessment API

## Overview

The **professional output level** is designed for energy consultants, advisors, and technical professionals who need detailed financial risk assessment with distribution analysis capabilities.

## Key Features

1. **Full Percentile Distributions** (P10-P90) for all 5 financial indicators
2. **Success Probability Metrics** for project viability assessment
3. **Chart Metadata** for client-side rendering of distribution graphs
4. **Comprehensive Statistics** for each indicator

---

## API Response Structure

### Example Request

```json
POST /risk-assessment

{
  "capex": 60000,
  "annual_maintenance_cost": 2000,
  "annual_energy_savings": 27400,
  "project_lifetime": 20,
  "loan_amount": 25000,
  "loan_term": 15,
  "output_level": "professional",
  "indicators": ["IRR", "NPV", "PBP", "DPP", "ROI"]
}
```

### Example Response

```json
{
  "point_forecasts": {
    "IRR": 5.7,
    "NPV": 5432.10,
    "ROI": 15.2,
    "PBP": 8.3,
    "DPP": 10.1
  },
  "percentiles": {
    "IRR": {
      "P10": 3.1,
      "P20": 4.0,
      "P30": 4.6,
      "P40": 5.2,
      "P50": 5.7,
      "P60": 6.3,
      "P70": 7.0,
      "P80": 7.9,
      "P90": 8.9
    },
    "NPV": {
      "P10": 2100.0,
      "P20": 3200.0,
      "P30": 4100.0,
      "P40": 4800.0,
      "P50": 5432.1,
      "P60": 6100.0,
      "P70": 6900.0,
      "P80": 7800.0,
      "P90": 9800.0
    },
    "ROI": { /* P10-P90 */ },
    "PBP": { /* P10-P90 */ },
    "DPP": { /* P10-P90 */ }
  },
  "probabilities": {
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
    "output_level": "professional",
    "indicators_requested": ["IRR", "NPV", "PBP", "DPP", "ROI"],
    "chart_metadata": {
      "NPV": { /* Chart data */ },
      "IRR": { /* Chart data */ },
      "ROI": { /* Chart data */ },
      "PBP": { /* Chart data */ },
      "DPP": { /* Chart data */ }
    }
  }
}
```

---

## Response Fields Explained

### 1. `point_forecasts`

**Type**: `Dict[str, float]`  
**Always included**

Median (P50) values for each requested indicator. These are the "expected" or "most likely" outcomes.

**Example**:
```json
{
  "IRR": 5.7,      // 5.7% annual return
  "NPV": 5432.10,  // €5,432 net profit over 20 years
  "ROI": 15.2,     // 15.2% total return on investment
  "PBP": 8.3,      // Breaks even in year 8.3
  "DPP": 10.1      // Discounted break-even in year 10.1
}
```

**Use case**: Display as primary metrics in dashboard summary.

---

### 2. `percentiles`

**Type**: `Dict[str, Dict[str, float]]`  
**Included in**: Professional, Public, Complete

Full percentile distributions showing the range of possible outcomes from pessimistic (P10) to optimistic (P90).

**Structure**:
```json
{
  "INDICATOR_NAME": {
    "P10": <value>,   // 10% of scenarios are worse than this
    "P20": <value>,
    "P30": <value>,
    "P40": <value>,
    "P50": <value>,   // Median (same as point_forecasts)
    "P60": <value>,
    "P70": <value>,
    "P80": <value>,
    "P90": <value>    // 10% of scenarios are better than this
  }
}
```

**Interpretation**:
- **P10**: Pessimistic scenario (only 10% of outcomes are worse)
- **P50**: Expected scenario (median)
- **P90**: Optimistic scenario (only 10% of outcomes are better)

**Use case**: Risk assessment, scenario planning, displaying uncertainty ranges.

---

### 3. `probabilities`

**Type**: `Dict[str, float]`  
**Included in**: Professional, Public, Complete

Success probability metrics answering key viability questions.

**Fields**:

| Key | Description | Example |
|-----|-------------|---------|
| `Pr(NPV > 0)` | Probability project is profitable | `0.8435` = 84.35% chance of profit |
| `Pr(PBP < Ny)` | Probability simple payback occurs within project lifetime | `0.9124` = 91.24% chance of payback |
| `Pr(DPP < Ny)` | Probability discounted payback occurs within project lifetime | `0.7563` = 75.63% chance of discounted payback |

**Use case**: 
- **High-confidence thresholds**: `> 0.90` (90%+) → Very safe investment
- **Moderate-confidence**: `0.70 - 0.90` → Acceptable risk for most projects
- **Low-confidence**: `< 0.70` → High risk, may require subsidies or longer horizon

---

### 4. `metadata.chart_metadata`

**Type**: `Dict[str, ChartMetadata]`  
**Location**: `response.metadata.chart_metadata`

Provides histogram bins, statistics, and configuration for generating distribution charts client-side.

**Structure for each indicator**:

```json
{
  "NPV": {
    "bins": {
      "centers": [1200.0, 1450.0, 1700.0, ..., 12500.0],  // X-axis bin centers
      "counts": [45, 123, 289, ..., 67],                   // Frequency in each bin
      "edges": [1075.0, 1325.0, 1575.0, ..., 12625.0]     // Bin boundaries
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
  }
}
```

#### Fields Explained

**`bins` object**:
- `centers`: X-coordinates for plotting histogram bars (30 bins)
- `counts`: Height of each bar (number of simulations in that bin)
- `edges`: Bin boundaries (31 values for 30 bins)

**`statistics` object**:
- `mean`: Arithmetic average of all simulations
- `std`: Standard deviation (measure of volatility/uncertainty)
- `P10`, `P50`, `P90`: Key percentiles for vertical reference lines

**`chart_config` object**:
- `xlabel`: Label for X-axis with units
- `ylabel`: Label for Y-axis
- `title`: Suggested chart title

---

## Chart Rendering Guide

### Recommended Visualization: Histogram with Percentile Lines

**Example using Chart.js**:

```javascript
const chartData = response.metadata.chart_metadata.NPV;

// Create histogram
const ctx = document.getElementById('npvChart').getContext('2d');
new Chart(ctx, {
  type: 'bar',
  data: {
    labels: chartData.bins.centers,
    datasets: [{
      label: 'Frequency',
      data: chartData.bins.counts,
      backgroundColor: 'rgba(54, 162, 235, 0.6)',
      borderColor: 'rgba(54, 162, 235, 1)',
      borderWidth: 1
    }]
  },
  options: {
    plugins: {
      title: {
        display: true,
        text: chartData.chart_config.title
      },
      annotation: {
        annotations: {
          p10: {
            type: 'line',
            xMin: chartData.statistics.P10,
            xMax: chartData.statistics.P10,
            borderColor: 'red',
            borderWidth: 2,
            label: {
              content: 'P10',
              enabled: true
            }
          },
          p50: {
            type: 'line',
            xMin: chartData.statistics.P50,
            xMax: chartData.statistics.P50,
            borderColor: 'orange',
            borderWidth: 3,
            label: {
              content: 'P50 (Median)',
              enabled: true
            }
          },
          p90: {
            type: 'line',
            xMin: chartData.statistics.P90,
            xMax: chartData.statistics.P90,
            borderColor: 'green',
            borderWidth: 2,
            label: {
              content: 'P90',
              enabled: true
            }
          }
        }
      }
    },
    scales: {
      x: {
        title: {
          display: true,
          text: chartData.chart_config.xlabel
        }
      },
      y: {
        title: {
          display: true,
          text: chartData.chart_config.ylabel
        }
      }
    }
  }
});
```

---

## Complete Professional Dashboard Layout

### Recommended Structure

```
┌─────────────────────────────────────────────────────────┐
│  PROJECT SUMMARY                                         │
│  • NPV: €5,432 (84% chance profitable)                  │
│  • IRR: 5.7% (P10: 3.1%, P90: 8.9%)                     │
│  • Payback: 8.3 years (91% chance within 20y lifetime)  │
└─────────────────────────────────────────────────────────┘

┌──────────────────┬──────────────────┬──────────────────┐
│  NPV Distribution│ IRR Distribution │ ROI Distribution │
│  [Histogram]     │  [Histogram]     │  [Histogram]     │
│  P10|P50|P90     │  P10|P50|P90     │  P10|P50|P90     │
└──────────────────┴──────────────────┴──────────────────┘

┌──────────────────────────┬──────────────────────────────┐
│  PBP Distribution        │  DPP Distribution            │
│  [Histogram]             │  [Histogram]                 │
│  P10|P50|P90             │  P10|P50|P90                 │
└──────────────────────────┴──────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  RISK ASSESSMENT                                         │
│  ✓ 84.35% probability of positive NPV                   │
│  ✓ 91.24% probability of payback within 20 years        │
│  ✓ 75.63% probability of discounted payback             │
└─────────────────────────────────────────────────────────┘
```

---

## Indicator Reference

### NPV (Net Present Value)
- **Unit**: Euros (€)
- **Meaning**: Total profit over project lifetime, accounting for time value of money
- **Target**: `> 0` (positive)
- **Interpretation**: 
  - `NPV > €10,000`: Excellent
  - `NPV > 0`: Profitable
  - `NPV < 0`: Loss-making

### IRR (Internal Rate of Return)
- **Unit**: Percentage (%)
- **Meaning**: Annual return rate that makes NPV = 0
- **Target**: `> discount_rate` (typically > 6%)
- **Interpretation**:
  - `IRR > 10%`: Excellent return
  - `IRR > 6%`: Good return
  - `IRR < 3%`: Poor return

### ROI (Return on Investment)
- **Unit**: Percentage (%)
- **Meaning**: Total profit as % of initial investment
- **Target**: `> 0`
- **Interpretation**:
  - `ROI > 50%`: Excellent
  - `ROI > 20%`: Good
  - `ROI < 10%`: Marginal

### PBP (Payback Period)
- **Unit**: Years
- **Meaning**: Time to recover initial investment (simple, no discounting)
- **Target**: `< project_lifetime / 2`
- **Interpretation**:
  - `PBP < 7y`: Fast payback
  - `PBP < 15y`: Acceptable
  - `PBP > 20y`: Very slow

### DPP (Discounted Payback Period)
- **Unit**: Years
- **Meaning**: Time to recover initial investment (accounting for time value)
- **Target**: `< project_lifetime`
- **Interpretation**:
  - Always longer than PBP
  - `DPP < 10y`: Fast payback
  - `DPP < 20y`: Acceptable
  - `DPP > 25y`: Very slow

---

## Testing the Endpoint

### Using cURL

```bash
curl -X POST https://api.relife.eu/risk-assessment \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "capex": 60000,
    "annual_maintenance_cost": 2000,
    "annual_energy_savings": 27400,
    "project_lifetime": 20,
    "loan_amount": 25000,
    "loan_term": 15,
    "output_level": "professional",
    "indicators": ["IRR", "NPV", "PBP", "DPP", "ROI"]
  }'
```

### Response Size

- **Typical size**: ~15-20 KB
- **With all 5 indicators**: ~20-25 KB
- **Compared to**:
  - Private output: ~8-10 KB
  - Complete output: ~500 KB - 2 MB (includes base64 images)

---

## FAQ

### Q: Can I request only specific indicators?

**A**: Yes! Use the `indicators` field to specify which KPIs to calculate:

```json
{
  "indicators": ["NPV", "IRR"],  // Only NPV and IRR
  ...
}
```

This reduces response size and computation time.

---

### Q: What's the difference between professional and complete output?

**A**: 
- **Professional**: Returns **metadata** for charts (bins, statistics) → Frontend renders charts
- **Complete**: Returns **base64-encoded images** → Backend renders charts, frontend displays directly

Professional is preferred for modern web apps (smaller response, interactive charts).

---

### Q: How are the histogram bins calculated?

**A**: 
- **30 bins** (optimal for 10,000 simulations)
- Bin edges automatically determined using NumPy's histogram algorithm
- Equal-width bins spanning from min to max value

---

### Q: Why are there 9 percentiles (P10-P90) instead of 7?

**A**: This provides a finer-grained distribution view:
- **3 percentiles** (P10/P50/P90): Basic risk range
- **5 percentiles** (P10/P25/P50/P75/P90): Standard quartiles
- **9 percentiles** (P10-P90 every 10%): Detailed distribution for professional analysis

---

## Related Documentation

- [Cash Flow Chart Metadata](./CASH_FLOW_CHART_METADATA.md) - Private output visualization
- [API User Inputs](./API_USER_INPUTS.md) - Complete endpoint specifications
- [Risk Assessment Documentation](./Risk_Assessment_Documentation.md) - Monte Carlo methodology

---

## Support

For questions or issues, contact the ReLIFE development team.
