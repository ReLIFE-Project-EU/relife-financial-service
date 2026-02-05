# ReLIFE PRA Tool - API Flow Diagram

**Professional Risk Assessment (PRA)**

This document shows the API flow for the PRA tool for professional consultants.

> **Main Difference from HMA:** The PRA tool uses `output_level: "professional"` (automatically set by frontend) to receive detailed risk distributions and chart metadata, while HMA uses `output_level: "private"` for simplified homeowner outputs.

> **Portfolio Analysis:** Portfolio aggregation (multiple buildings) is handled at the frontend/forecasting level. The Financial API processes aggregated values as a single request with professional output.

> **See Also:** [ReLIFE_HMA_flowchart.md](./ReLIFE_HMA_flowchart.md) for the homeowner version (HMA).

---

## Output Level Comparison

| Aspect | HMA (Private) | PRA (Professional) |
|--------|---------------|-------------------|
| **Output Level** | `"private"` | `"professional"` |
| **Target Users** | Homeowners | Energy consultants, advisors |
| **Percentiles** | P10-P90 for all indicators | P10-P90 for all indicators |
| **Success Metrics** | MonthlyAvgSavings, SuccessRate | 3 Probabilities (NPV>0, PBP<lifetime, DPP<lifetime) |
| **Visualization** | cash_flow_data (1 timeline chart) | chart_metadata (5 distribution histograms) |
| **Response Size** | ~10 KB | ~20 KB |

For detailed comparison, see [PRIVATE_VS_PROFESSIONAL_OUTPUT.md](../PRIVATE_VS_PROFESSIONAL_OUTPUT.md).

---

## Key Differences: PRA vs HRA

| Feature | HRA (Private) | PRA (Professional) |
|---------|---------------|-------------------|
| **Target Audience** | Individual homeowners | Energy consultants, advisors |
## API Call Flow

> **Note:** Portfolio aggregation (analyzing multiple buildings) happens at frontend/forecasting level. The Financial API receives aggregated values and processes them as a single analysis with professional output.

```mermaid
sequenceDiagram
    actor Professional as Energy Consultant
    participant Frontend
    participant DB as ReLIFE Database
    participant Forecasting as Forecasting API
    participant Financial as Financial API
    participant Technical as Technical API (MCDA)
    
    Professional->>Frontend: Enter building details<br/>(or portfolio - aggregated at frontend)
    Frontend->>DB: Retrieve archetype/CAPEX data
    DB-->>Frontend: CAPEX, maintenance, Building Archetypes
    
    Note over Frontend,Forecasting: Step 1: Energy Simulation
    Frontend->>Forecasting: POST /[ENDPOINT]<br/>(building inputs or aggregated portfolio)
    Forecasting-->>Frontend: energy_savings, energy_class_before,<br/>energy_class_after, emissions
    
    Note over Frontend,Financial: Step 2: Financial Analysis (Professional Output)
    Frontend->>Financial: POST /arv<br/>(energy_class_before)
    Financial-->>Frontend: property_value_before
    Frontend->>Financial: POST /arv<br/>(energy_class_after)
    Financial-->>Frontend: property_value_after
    Frontend->>Financial: POST /risk-assessment<br/>(output_level: "professional")
    Financial-->>Frontend: Percentiles P10-P90<br/>Probabilities (3 metrics)<br/>Chart metadata (5 distributions)
    
    Note over Frontend,Technical: Step 3: Multi-Criteria Decision Analysis
    Frontend->>Technical: POST /mcda<br/>(forecasting outputs + financial data)
    Technical-->>Frontend: Optimal renovation packages<br/>Scenario analysis<br/>Cost-benefit tradeoffs
    
    Frontend->>Professional: Display comprehensive results:<br/>- Risk distributions (5 charts)<br/>- Success probabilities<br/>- Optimal packages<br/>- Multi-criteria rankings
```

---

## 1. API Component Inputs & Outputs

### Forecasting API

> **To be revised by Daniele**  
> 
> See [ReLIFE_HMA_flowchart.md](./ReLIFE_HMA_flowchart.md) for current Forecasting API structure.

---

### Financial API

**All inputs and outputs are identical to HMA** - see [ReLIFE_HMA_flowchart.md](./ReLIFE_HMA_flowchart.md) for complete Financial API documentation (/arv and /risk-assessment endpoints).

**Key Difference:**
- **HMA tool:** `output_level: "private"` (automatically set by frontend)
- **PRA tool:** `output_level: "professional"` (automatically set by frontend)

This is the **only difference** between HMA and PRA for the Financial API. The `output_level` parameter determines the response structure:
- **Private:** Returns `cash_flow_data` (for timeline chart), `MonthlyAvgSavings`, `SuccessRate`
- **Professional:** Returns `chart_metadata` (for 5 distribution charts), `probabilities` (3 success metrics)

Both return `percentiles` (P10-P90) for all requested indicators.

---

### Technical API (Multi-Criteria Decision Analysis)

> **To be revised by Eric**  
> 
> Technical API documentation for PRA tool will be provided.

---

### Portfolio Mode Support

The PRA tool supports two modes:

1. **Single Building Analysis** - Same inputs as HRA, but with professional-level outputs
2. **Portfolio Analysis** - Analyze multiple buildings simultaneously with aggregated results

#### Portfolio-Specific Inputs

When analyzing a portfolio, the following additional structure is used:

```json
{
  "analysis_mode": "portfolio",  // "single" or "portfolio"
  "buildings": [
    {
      "building_id": "BLD-001",
      "name": "Office Building A",
      // ... standard building inputs for Forecasting API ...
    },
    {
      "building_id": "BLD-002", 
      "name": "Apartment Complex B",
      // ... standard building inputs ...
    }
  ],
  "portfolio_constraints": {
    "total_budget": 500000,  // Total CAPEX budget across all buildings
    "implementation_phasing": true,  // Allow multi-year implementation
    "priority_weighting": {
      "financial_roi": 0.4,
      "energy_savings": 0.3,
      "emissions_reduction": 0.2,
      "social_impact": 0.1
    }
  }
}
```

---

### Forecasting API

**Required Inputs:** *(Same as HRA - see [ReLIFE_HMA_flowchart.md](./ReLIFE_HMA_flowchart.md) for complete details)*

#### Building
- `name`, `azimuth_relative_to_true_north`, `latitude`, `longitude`
- `exposed_perimeter`, `height`, `wall_thickness`, `n_floors`
- `building_type_class`, `net_floor_area`

#### Envelope Elements: `"building_surface"`
- Surface definitions (opaque, transparent, adiabatic, adjacent)
- Common attributes: `area`, `u_value`, `orientation`, `thermal_capacity`
- Transparent surface attributes: `g_value`, `shading`, window dimensions

#### System Parameters
- Emitter block, Distribution block, Generator block
- Control strategies, Efficiency models

**Portfolio Mode:**
- When `analysis_mode: "portfolio"`, Forecasting API processes multiple buildings
- Returns individual results + aggregated portfolio metrics

---

### Financial API

**Required Inputs from User:**
- `project_lifetime` (int, 1-30 years)
- Property location: `lat`, `lng`
- Property details: `floor_area`, `construction_year`, `number_of_floors`, `property_type`

**Optional Inputs from User:**
- `capex` (float) - If not provided, retrieved from database
- `annual_maintenance_cost` (float) - If not provided, retrieved from database  
- `loan_amount` (float, default: 0.0)
- `loan_term` (int, default: 0)
- `floor_number` (int, default: null)
- `renovated_last_5_years` (bool, default: true)

**Frontend-Defined Inputs:**
- `output_level` (string) - **Automatically set to `"professional"`** for PRA tool
  - HRA tool uses `"private"`
  - PRA tool uses `"professional"` ← **Key Difference**
  
**Portfolio Mode:**
- `analysis_mode: "portfolio"` (optional, triggers portfolio aggregation)
- `building_ids: []` (array of building IDs being analyzed)

**Data from ReLIFE Database:**
- `capex` (when not provided by user)
- `annual_maintenance_cost` (when not provided by user)

---

### Technical API (MCDA)

**Required Inputs:**
- Financial percentiles (NPV, IRR, ROI, PBP, DPP) at P10-P90
- Success probabilities from Financial API
- Energy performance metrics from Forecasting API
- Environmental impact data (CO2, emissions)

**Portfolio-Specific Inputs:**
- Building-level results for each property in portfolio
- Budget constraints and phasing requirements
- Priority weighting matrix

**Outputs:**
- Ranked renovation scenarios using TOPSIS/AHP
- Optimal technology packages per building
- Portfolio-level recommendations
- Cost-benefit tradeoff analysis
- Implementation phasing plan (for portfolios)

---

## 2. Professional Output Visualization

### Distribution Charts (5 charts)

The professional output provides **histogram metadata** for client-side rendering of 5 distribution charts:

1. **NPV Distribution** - Net Present Value outcomes
2. **IRR Distribution** - Internal Rate of Return spread
3. **ROI Distribution** - Return on Investment variability
4. **PBP Distribution** - Simple Payback Period range
5. **DPP Distribution** - Discounted Payback Period uncertainty

Each chart displays:
- Histogram of 10,000 Monte Carlo simulation results
- Vertical lines at P10 (pessimistic), P50 (median), P90 (optimistic)
- Mean and standard deviation statistics
- Risk/uncertainty visualization

**Chart Rendering Example (Chart.js):**
```javascript
const chartData = response.metadata.chart_metadata.NPV;

new Chart(ctx, {
  type: 'bar',
  data: {
    labels: chartData.bins.centers,
    datasets: [{
      label: 'Frequency',
      data: chartData.bins.counts,
      backgroundColor: 'rgba(54, 162, 235, 0.6)'
    }]
  },
  options: {
    plugins: {
      title: { text: chartData.chart_config.title },
      annotation: {
        annotations: {
          p10: {
            type: 'line',
            xMin: chartData.statistics.P10,
            xMax: chartData.statistics.P10,
            borderColor: 'red',
            label: { content: 'P10 (Pessimistic)' }
          },
          p50: {
            type: 'line',
            xMin: chartData.statistics.P50,
            xMax: chartData.statistics.P50,
            borderColor: 'orange',
            label: { content: 'P50 (Expected)' }
          },
          p90: {
            type: 'line',
            xMin: chartData.statistics.P90,
            xMax: chartData.statistics.P90,
            borderColor: 'green',
            label: { content: 'P90 (Optimistic)' }
          }
        }
      }
    }
  }
});
```

---

## 4. Frontend Implementation

### Sequential Flow

```mermaid
flowchart TD
    ProfessionalInput[PROFESSIONAL INPUT<br/>---<br/>Mode: Single or Portfolio<br/>---<br/>Single Building:<br/>- Building details<br/>- Location lat, lng<br/>- Project lifetime<br/>---<br/>Portfolio:<br/>- Multiple building inputs<br/>- Budget constraints<br/>- Priority weighting]
    
    DB[(ReLIFE Database<br/>---<br/>CAPEX<br/>Maintenance costs<br/>Building Archetypes<br/>Historical data)]
    
    Forecasting[FORECASTING SERVICE<br/>---<br/>Single or Portfolio mode<br/>---<br/>Outputs:<br/>- energy_savings<br/>- energy_class_before<br/>- energy_class_after<br/>- CO2 emissions<br/>- Portfolio aggregation]
    
    FinancialARV[FINANCIAL SERVICE - ARV<br/>---<br/>POST /arv twice per building<br/>---<br/>Calculates:<br/>- Property value before<br/>- Property value after<br/>- Net ARV gain<br/>---<br/>Portfolio: loops all buildings]
    
    FinancialRisk[FINANCIAL SERVICE - RISK<br/>---<br/>POST /risk-assessment<br/>output_level: professional<br/>---<br/>Returns:<br/>- Percentiles P10-P90<br/>- 3 Probabilities<br/>- 5 Chart metadata<br/>---<br/>Portfolio: aggregated results]
    
    TechnicalMCDA[TECHNICAL SERVICE - MCDA<br/>---<br/>POST /mcda<br/>---<br/>Multi-Criteria Analysis:<br/>- TOPSIS ranking<br/>- Scenario comparison<br/>- Optimal packages<br/>- Portfolio optimization<br/>- Phasing plan]
    
    ProfessionalUI[PROFESSIONAL UI<br/>---<br/>Display:<br/>- 5 Distribution charts<br/>- Risk probabilities<br/>- Scenario rankings<br/>- Portfolio analysis<br/>- Implementation plan<br/>- Cost-benefit tradeoffs]
    
    ProfessionalInput --> Forecasting
    DB --> Forecasting
    
    ProfessionalInput --> FinancialARV
    DB --> FinancialARV
    Forecasting --> FinancialARV
    
    Forecasting --> FinancialRisk
    FinancialARV --> FinancialRisk
    
    Forecasting --> TechnicalMCDA
    FinancialARV --> TechnicalMCDA
    FinancialRisk --> TechnicalMCDA
    
    Forecasting --> ProfessionalUI
    FinancialARV --> ProfessionalUI
    FinancialRisk --> ProfessionalUI
    TechnicalMCDA --> ProfessionalUI
    
    style ProfessionalInput fill:#f0f0f0
    style DB fill:#d4edda
    style Forecasting fill:#cfe2ff
    style FinancialARV fill:#fff3cd
    style FinancialRisk fill:#fff3cd
    style TechnicalMCDA fill:#f8d7da
    style ProfessionalUI fill:#d1ecf1
```

---

## 5. Key Implementation Notes

### Automatic Output Level Detection

The frontend **automatically sets** `output_level` based on the tool:
- **HRA tool** → `output_level: "private"`
- **PRA tool** → `output_level: "professional"`

**Users never select this manually** - it's determined by which tool they're using.

### Portfolio Aggregation Strategy

When analyzing a portfolio:

1. **Forecasting API** returns individual + aggregated energy results
2. **Financial API** processes each building separately for ARV
3. **Financial API** aggregates risk assessment at portfolio level
4. **Technical API** performs portfolio-wide optimization considering:
   - Budget constraints
   - Implementation dependencies
   - Priority weighting
   - Multi-year phasing

### Response Size Considerations

- **Single Building (Professional):** ~18-25 KB
  - Larger than HRA due to chart metadata (5 distributions × 30 bins each)
  
- **Portfolio (3-5 Buildings):** ~80-120 KB
  - Scales with number of buildings
  - Each building includes full chart metadata
  - Portfolio-level aggregations add overhead

### Visualization Differences

| Output Level | HRA (Private) | PRA (Professional) |
|--------------|---------------|-------------------|
| Cash Flow Timeline | ✅ 1 chart (years vs cumulative cash flow) | ❌ Not included |
| Distribution Histograms | ❌ Not included | ✅ 5 charts (NPV, IRR, ROI, PBP, DPP) |
| Metadata Field | `cash_flow_data` | `chart_metadata` |
| Chart Type | Line/area chart | Histogram with percentile lines |
| Frontend Rendering | Simple timeline plot | Statistical distributions with P10/P50/P90 |

---

## 6. Related Documentation

- **[ReLIFE_HMA_flowchart.md](./ReLIFE_HMA_flowchart.md)** - Private homeowner version (HRA tool)
- **[PRIVATE_VS_PROFESSIONAL_OUTPUT.md](../PRIVATE_VS_PROFESSIONAL_OUTPUT.md)** - Detailed comparison of output levels
- **[PROFESSIONAL_OUTPUT_DOCUMENTATION.md](../PROFESSIONAL_OUTPUT_DOCUMENTATION.md)** - Complete professional API guide
- **[CASH_FLOW_CHART_METADATA.md](../CASH_FLOW_CHART_METADATA.md)** - Private output visualization guide
- **[Risk_Assessment_Documentation.md](../Risk_Assessment_Documentation.md)** - Monte Carlo methodology

---

**Last Updated:** February 5, 2026  
**Version:** 1.0  
**Tool:** Professional Risk Assessment (PRA)
