# Cash Flow Chart Metadata Documentation

## Summary

The **private output level** of the Risk Assessment API now returns comprehensive cash flow data as **metadata** (not as rendered images), enabling the frontend to render interactive charts client-side.

## API Response Structure

### Response Fields

```json
{
  "point_forecasts": {
    "NPV": 5432.10,
    "IRR": 5.7,
    "ROI": 15.2,
    "PBP": 8.3,
    "DPP": 10.1,
    "MonthlyAvgSavings": 345.64,
    "SuccessRate": 0.843
  },
  "percentiles": {
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
    "IRR": { "P10": ..., "P20": ..., ... },
    "ROI": { "P10": ..., "P20": ..., ... },
    "PBP": { "P10": ..., "P20": ..., ... },
    "DPP": { "P10": ..., "P20": ..., ... }
  },
  "metadata": {
    "n_sims": 10000,
    "project_lifetime": 20,
    "capex": 60000,
    "annual_maintenance_cost": 250,
    "annual_energy_savings": 27400,
    "loan_amount": 20000,
    "loan_term": 15,
    "annual_loan_payment": 1737.50,
    "loan_rate_percent": 3.5,
    "cash_flow_data": {
      // 👇 THIS IS THE KEY FIELD FOR CHART RENDERING
      "years": [0, 1, 2, 3, ..., 20],
      "initial_investment": 40000.0,
      "annual_inflows": [0.0, 6740.40, 6959.60, ..., 11500.00],
      "annual_outflows": [40000.0, 1994.00, 2000.95, ..., 350.00],
      "annual_net_cash_flow": [40000.0, 4746.40, 4958.65, ..., 11150.00],
      "cumulative_cash_flow": [-40000.0, -35253.60, -30294.96, ..., 103477.16],
      "breakeven_year": 8,
      "loan_term": 15
    }
  }
}
```

## Cash Flow Data Structure

### Location
`response.metadata.cash_flow_data`

### Fields Explained

#### `years: number[]`
- **Purpose**: X-axis values for the timeline
- **Example**: `[0, 1, 2, ..., 20]`
- **Length**: `project_lifetime + 1` (includes Year 0)

#### `initial_investment: number`
- **Purpose**: Out-of-pocket investment at Year 0
- **Calculation**: `CAPEX - loan_amount`
- **Example**: €40,000 (if CAPEX=60k, loan=20k)

#### `annual_inflows: number[]`
- **Purpose**: Revenue from energy savings each year
- **Year 0**: Always `0.0` (no inflows in investment year)
- **Years 1-N**: Energy savings × electricity price (with price projections)
- **Example**: `[0.0, 6740.40, 6959.60, ..., 11500.00]`
- **Use**: Render as **green bars** in chart

#### `annual_outflows: number[]`
- **Purpose**: Total costs each year (maintenance + loan payments)
- **Year 0**: Equals `initial_investment` (capital outlay)
- **Years 1-N**: Maintenance costs (inflated) + loan payments (if applicable)
- **Example**: `[40000.0, 1994.00, 2000.95, ..., 350.00]`
- **Use**: Render as **red bars** in chart

#### `annual_net_cash_flow: number[]`
- **Purpose**: Net position each year (inflows - outflows)
- **Calculation**: `annual_inflows[i] - annual_outflows[i]`
- **Example**: `[40000.0, 4746.40, 4958.65, ..., 11150.00]`
- **Use**: Render as **line overlay** showing net benefit

#### `cumulative_cash_flow: number[]`
- **Purpose**: Running total of cash position over time
- **Year 0**: Negative initial investment
- **Interpretation**: When this crosses 0, the project breaks even
- **Example**: `[-40000.0, -35253.60, -30294.96, ..., 103477.16]`
- **Use**: Render as **cumulative line** or use for break-even annotation

#### `breakeven_year: number | null`
- **Purpose**: Year when cumulative cash flow becomes positive
- **Example**: `8` (project breaks even in year 8)
- **Null case**: Project never breaks even within lifetime
- **Use**: Add **vertical marker** at this year with annotation

#### `loan_term: number | null`
- **Purpose**: Year when loan is fully paid off
- **Example**: `15` (loan paid off after 15 years)
- **Null case**: No loan (all-equity financing)
- **Use**: Add **vertical marker** at this year with annotation

## Chart Rendering Guide

### Recommended Visualization

```
Annual Cash Flow Timeline
══════════════════════════════════════════════════════════════

     €12k ┤                                           ╭──────────
          │                                      ╭────┤ Inflows
     €10k ┤                                 ╭────┤
          │                            ╭────┤
      €8k ┤                       ╭────┤
          │                  ╭────┤
      €6k ┤             ╭────┤
          │        ╭────┤             Break-even↓    Loan Paid↓
      €4k ┤   ╭────┤                        │           │
          │───┴────┴────┬────┬────┬────┬────┼───┬───┬──┼───┬───
      €0  ├─────────────┼────┼────┼────┼────┼───┼───┼──┼───┼───
          │             │    │    │    │    │   │   │  │   │
    -€40k ┤█████        │    │    │    │    │   │   │  │   │
          │ Out-        ▓    ▓    ▓    ▓    ▓   ▓   ▓  ▓   ▓
          │ flow        ▓    ▓    ▓    ▓    ▓   ▓   ▓  ▓   ▓
          └─────────────┴────┴────┴────┴────┴───┴───┴──┴───┴───
            0   1   2   3   4   5   6   7   8   9  10  15  20
                           Year
```

### Implementation Tips

1. **Bar Chart (Stacked or Grouped)**
   - Green bars: `annual_inflows`
   - Red bars: `annual_outflows`
   - Position bars using `years` array

2. **Line Overlay**
   - Dark line: `annual_net_cash_flow` or `cumulative_cash_flow`
   - Shows trend toward profitability

3. **Milestone Markers**
   - Vertical line at `breakeven_year` with green annotation
   - Vertical line at `loan_term` with orange annotation

4. **Value Labels**
   - Add labels every 5 years to avoid clutter
   - Format: `€{value/1000}k` (e.g., "€6.7k")

5. **Tooltips (Interactive)**
   - On hover, show all values for that year
   - Format:
     ```
     Year 8
     Inflows: €8,234.50
     Outflows: €1,987.20
     Net: €6,247.30
     Cumulative: €3,921.71 ✓ Break-even!
     ```

## Validation

The metadata has been validated to ensure:
- ✅ All required fields present
- ✅ Array lengths match project lifetime + 1
- ✅ Year 0 conditions correct (no inflows, outflows = initial investment)
- ✅ Cumulative cash flow logic correct
- ✅ Break-even calculation accurate
- ✅ Loan term metadata matches request

## Example: Accessing in JavaScript

```javascript
// Parse API response
const response = await fetch('/api/risk-assessment', {
  method: 'POST',
  body: JSON.stringify(requestData)
});
const data = await response.json();

// Extract chart data
const chartData = data.metadata.cash_flow_data;

// Example: Render with Chart.js
const ctx = document.getElementById('cashFlowChart').getContext('2d');
new Chart(ctx, {
  type: 'bar',
  data: {
    labels: chartData.years,
    datasets: [
      {
        label: 'Inflows',
        data: chartData.annual_inflows,
        backgroundColor: 'rgba(39, 174, 96, 0.8)',
        borderColor: 'rgba(39, 174, 96, 1)',
        borderWidth: 1
      },
      {
        label: 'Outflows',
        data: chartData.annual_outflows.map(v => -v), // Negate for display
        backgroundColor: 'rgba(231, 76, 60, 0.8)',
        borderColor: 'rgba(231, 76, 60, 1)',
        borderWidth: 1
      }
    ]
  },
  options: {
    responsive: true,
    plugins: {
      annotation: {
        annotations: {
          breakeven: {
            type: 'line',
            xMin: chartData.breakeven_year,
            xMax: chartData.breakeven_year,
            borderColor: 'green',
            borderWidth: 2,
            label: {
              content: `Break-even (Year ${chartData.breakeven_year})`,
              enabled: true
            }
          }
        }
      }
    }
  }
});
```

## Why Metadata Instead of Rendered Image?

Previously, charts were returned as base64-encoded PNG images (500 KB - 2 MB). Now:

✅ **Smaller Response Size**: ~2-5 KB instead of 500 KB  
✅ **Frontend Flexibility**: Can customize styling, colors, interactivity  
✅ **Responsive**: Charts adapt to different screen sizes  
✅ **Accessible**: Screen readers can access data  
✅ **Interactive**: Hover tooltips, zooming, filtering  
✅ **Consistent UX**: Matches frontend design system  

## Questions?

If you need different data formats or additional fields for rendering, update the `_build_private_output()` function in:
`src/relife_financial/services/risk_assessment.py`
