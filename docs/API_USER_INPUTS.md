# API User Inputs Documentation

**Date:** January 9, 2026  
**Purpose:** Frontend integration reference for ReLIFE Financial Service APIs

This document lists all user inputs required and optional for each API endpoint.

---

## 1. Risk Assessment Endpoint

**Endpoint:** `POST /risk-assessment`  
**Purpose:** Perform comprehensive Monte Carlo risk assessment for energy retrofit projects

### Required Inputs

| Parameter | Type | Description | Constraints |
|-----------|------|-------------|-------------|
| `annual_energy_savings` | float | Annual energy savings in kWh (from energy analysis API) | > 0 |
| `project_lifetime` | integer | Project evaluation horizon in years | 1-30 years |
| `output_level` | string | Detail level (auto-determined by frontend tool) | `"private"`, `"professional"`, `"public"`, or `"complete"` |

### Optional Inputs (with defaults)

| Parameter | Type | Description | Default | Constraints |
|-----------|------|-------------|---------|-------------|
| `capex` | float | Capital expenditure (total investment cost) in € | `null` (falls back to internal dataset) | > 0 if provided |
| `annual_maintenance_cost` | float | Annual maintenance/operational cost in € | `null` (falls back to internal dataset) | ≥ 0 if provided |
| `loan_amount` | float | Loan amount in € | `0.0` (all-equity financing) | ≥ 0, cannot exceed `capex` |
| `loan_term` | integer | Loan repayment term in years | `0` | ≥ 0, must be > 0 if `loan_amount` > 0 |
| `indicators` | array of strings | Financial KPIs to calculate | `["IRR", "NPV", "PBP", "DPP", "ROI"]` | Valid values: `"IRR"`, `"NPV"`, `"PBP"`, `"DPP"`, `"ROI"` |
| `include_visualizations` | boolean | Force include/exclude charts | `null` (follows `output_level`) | Only `"complete"` includes visualizations by default |

### Validation Rules
- If `loan_amount > 0`, then `loan_term` must be `> 0`
- `loan_amount` cannot exceed `capex` (when capex is provided)
- `loan_term` cannot exceed `project_lifetime`
- At least one indicator must be specified in `indicators`

### Example Request
```json
{
  "capex": 60000,
  "annual_energy_savings": 27400,
  "annual_maintenance_cost": 2000,
  "project_lifetime": 20,
  "loan_amount": 25000,
  "loan_term": 15,
  "output_level": "private",
  "indicators": ["NPV", "PBP", "ROI", "IRR"]
}
```

---

## 2. After Renovation Value (ARV) Endpoint

**Endpoint:** `POST /arv`  
**Purpose:** Predict property value after energy renovation using trained LightGBM model

### Required Inputs

| Parameter | Type | Description | Constraints |
|-----------|------|-------------|-------------|
| `lat` | float | Latitude coordinate | -90 to 90 |
| `lng` | float | Longitude coordinate | -180 to 180 |
| `floor_area` | float | Usable floor area in m² | > 0 |
| `construction_year` | integer | Year the building was constructed | 1800-2030 |
| `number_of_floors` | integer | Total floors in the building | 1-100 |
| `property_type` | string | Type of property | See valid options below |
| `energy_class` | string | EPC label after renovation | See valid options below |

#### Valid Property Types
- `"Loft"`
- `"Studio / Bedsit"`
- `"Villa"`
- `"Apartment"`
- `"Building"`
- `"Other"`
- `"Maisonette"`
- `"Detached House"`
- `"Apartment Complex"`

#### Valid Energy Classes (ordered from worst to best)
- `"Η"` (worst)
- `"Ζ"`
- `"Ε"`
- `"Δ"`
- `"Γ"`
- `"Β"`
- `"Β+"`
- `"Α"`
- `"Α+"` (best)

### Optional Inputs (with defaults)

| Parameter | Type | Description | Default | Constraints |
|-----------|------|-------------|---------|-------------|
| `floor_number` | integer | Floor level where property is located (0=ground floor) | `null` (not applicable for houses) | Must be < `number_of_floors` if provided |
| `renovated_last_5_years` | boolean | Whether property was recently renovated | `true` | - |

### Validation Rules
- `floor_number` must be less than `number_of_floors` (if provided)
- For detached houses, `floor_number` can be `null`

### Example Request
```json
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

## Notes for Frontend Implementation

### Authentication
Both endpoints require JWT authentication. Include the token in the Authorization header:
```
Authorization: Bearer <jwt_token>
```

### Output Levels (Risk Assessment)
The `output_level` parameter should be automatically determined by the frontend tool context:
- **`"private"`** - Individual homeowners tool (basic metrics + intuitive summaries/graphs, ~2 KB)
- **`"professional"`** - Energy consultants tool (detailed analysis, ~5 KB)
- **`"public"`** - Public institutions tool (comprehensive reports, ~10 KB)
- **`"complete"`** - Special cases requiring full charts (includes visualizations, ~500 KB - 2 MB)

### Data Flow
1. User inputs property/project details in frontend
2. Frontend calls energy analysis API → gets `annual_energy_savings` and `energy_class`
3. Frontend calls `/arv` endpoint → gets property value after renovation
4. Frontend calls `/risk-assessment` endpoint → gets financial risk assessment
5. Display results to user based on `output_level`

### Error Handling
Both endpoints return standard HTTP error codes:
- **400 Bad Request** - Invalid input parameters or validation errors
- **401 Unauthorized** - Missing or invalid JWT token
- **500 Internal Server Error** - Server-side processing errors

---

## Questions or Issues?

For technical questions about these endpoints, contact the backend development team.
