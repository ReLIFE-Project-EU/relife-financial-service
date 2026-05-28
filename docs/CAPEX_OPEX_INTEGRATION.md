# CAPEX / OPEX Lookup Integration

> Implementation plan for making `capex` and `annual_maintenance_cost` optional in the
> risk assessment endpoint by resolving them from the bundled Excel reference data.

---

## Source files

| File | Location | Rows | Notes |
|---|---|---|---|
| `ReLIFE_CAPEX.xlsx` | `src/relife_financial/data/` | 325 data rows | Use this. Has sources column. |
| `ReLIFE_OPEX.xlsx` | `src/relife_financial/data/` | 27 data rows | One row per country. |
| `capex_opex.xlsx` | `src/relife_financial/data/` | 288 data rows | Legacy / older version — do **not** use. |

---

## CAPEX file structure

**Sheet:** `Foglio1` — 325 rows × 17 columns

| Column | Name | Notes |
|---|---|---|
| B | Country | 27 EU countries |
| C | Region | Mostly `"General"`; Spain has `"Madrid"` for some actions |
| D | Renovation work | One of 10 action strings (see below) |
| E | Material | Insulation material (EPS / MW / GW) or window frame (PVC / Al / Wood); `None` for HVAC |
| F | Thickness [cm] | Insulation thickness — context only, not needed for lookup |
| L | Price [€/m²] | Used for insulation and windows |
| M | Price [€] | Fixed installation cost for HVAC / PV / Solar; occasionally set for a few PV rows |
| N | Price [€/kW] | Capacity-based cost for HVAC / PV / Solar |

### The 10 renovation actions (canonical names — exact string match required)

| # | Action name | Price unit | User quantity needed |
|---|---|---|---|
| 1 | `Wall insulation` | €/m² | `area_m2` |
| 2 | `Wall insulation - additional` | €/m² | `area_m2` |
| 3 | `Roof insulation - Accessible` | €/m² | `area_m2` |
| 4 | `Roof insulation - Makeover` | €/m² | `area_m2` |
| 5 | `Floor insulation` | €/m² | `area_m2` |
| 6 | `Windows` | €/m² | `area_m2` |
| 7 | `Air-water Heat Pump` | €/kW + fixed € | `capacity_kw` |
| 8 | `Condensing boiler` | €/kW + fixed € | `capacity_kw` |
| 9 | `PV` | €/kW (+ fixed € for 3 countries) | `capacity_kw` |
| 10 | `Solar thermal panels` | €/kW + fixed € | `capacity_kw` |

### CAPEX computation per action

```
area-based:     capex_action = Price[€/m²] × area_m2
capacity-based: capex_action = Price[€] + Price[€/kW] × capacity_kw
```

For capacity-based actions, `Price[€]` (fixed installation cost) and `Price[€/kW]` (capacity
cost) must **both** be summed. At typical residential sizes the fixed cost dominates — e.g.
Austria Heat Pump: €12,193 fixed + €1,742/kW × 7 kW ≈ €24,386 total.

**Total CAPEX** = sum of `capex_action` across all selected renovation actions.

### Multiple rows per country × action (material variants)

Several country × action combinations have 2–3 rows differing only by material:

| Country | Action | Materials |
|---|---|---|
| Croatia | Wall insulation | EPS, MW, GW |
| Croatia | Wall insulation - additional | EPS, MW, GW |
| Czech Republic | Wall insulation | 2 variants |
| Czech Republic | Wall insulation - additional | 2 variants |
| Greece | Windows | 2 variants |
| Italy | Windows | 3 variants |
| Netherlands | Windows | 3 variants |
| Spain | Wall insulation | 2 variants |
| Spain | Wall insulation - additional | 2 variants |
| Spain | Roof insulation - Makeover | 2 variants |
| Spain | Floor insulation | 3 variants |
| Spain | Windows | 3 variants (PVC / Al / Wood) |

**Resolution strategy (agreed):** average `Price[€/m²]` across all materials for that
country × action unless the caller specifies `material` explicitly.

---

## OPEX file structure

**Sheet:** `Foglio1` — 27 rows × 5 columns

| Column | System | Maps to renovation action |
|---|---|---|
| B | Heat Pump | `Air-water Heat Pump` |
| C | Gas Boiler | `Condensing boiler` |
| D | PV | `PV` |
| E | Solar Thermal | `Solar thermal panels` |

Values are **flat annual O&M costs (€/year)** — country-average, not scaled by area or capacity.
Insulation and Windows have no OPEX entry (near-zero maintenance).

**Total annual_maintenance_cost** = sum of OPEX values for each selected action that has an
entry in the OPEX table.

---

## Country name mismatch

| CAPEX file | OPEX file | Canonical name to use in API |
|---|---|---|
| `Czech Republic` | `Czechia` | Either — normalise on load |

All other 26 country names are identical between both files.

**27 supported countries:** Austria, Belgium, Bulgaria, Croatia, Cyprus, Czech Republic /
Czechia, Denmark, Estonia, Finland, France, Germany, Greece, Hungary, Ireland, Italy,
Latvia, Lithuania, Luxembourg, Malta, Netherlands, Poland, Portugal, Romania, Slovakia,
Slovenia, Spain, Sweden.

---

## Implementation plan

### Step 1 — New data module: `src/relife_financial/data/lookup.py`

- Load both Excel files at **module import time** (cached as module-level dicts).
- Build two lookup structures:
  ```python
  # capex_table[(country_normalised, action)] = list[dict] of rows
  # opex_table[country_normalised] = dict(action -> annual_cost)
  ```
- Normalise country names to a single canonical form on load.
- Expose:
  ```python
  def compute_capex(country: str, actions: list[RenovationAction]) -> float: ...
  def compute_opex(country: str, actions: list[RenovationAction]) -> float: ...
  def supported_countries() -> list[str]: ...
  def supported_actions() -> list[str]: ...
  ```
- Raise `ValueError` with a clear message if country or action name is not found.

### Step 2 — New Pydantic model in `models/risk_assessment.py`

```python
class RenovationAction(BaseModel):
    action: str = Field(
        ...,
        description="Renovation work type. Must be one of the 10 supported action names."
    )
    area_m2: float | None = Field(
        default=None, gt=0,
        description="Surface area in m² (required for insulation and windows actions)."
    )
    capacity_kw: float | None = Field(
        default=None, gt=0,
        description="System capacity in kW (required for HVAC, PV, and solar actions)."
    )
    material: str | None = Field(
        default=None,
        description=(
            "Optional material variant (e.g. EPS, MW, GW for wall insulation; "
            "PVC, Al, Wood for windows). If omitted and multiple variants exist, "
            "the average price is used."
        )
    )

    @model_validator(mode="after")
    def check_quantity(self) -> RenovationAction:
        area_actions = {
            "Wall insulation", "Wall insulation - additional",
            "Roof insulation - Accessible", "Roof insulation - Makeover",
            "Floor insulation", "Windows",
        }
        if self.action in area_actions and self.area_m2 is None:
            raise ValueError(f"area_m2 is required for action '{self.action}'")
        capacity_actions = {
            "Air-water Heat Pump", "Condensing boiler", "PV", "Solar thermal panels"
        }
        if self.action in capacity_actions and self.capacity_kw is None:
            raise ValueError(f"capacity_kw is required for action '{self.action}'")
        return self
```

### Step 3 — Update `RiskAssessmentRequest` in `models/risk_assessment.py`

Change `capex` and `annual_maintenance_cost` from required to optional, and add two new fields:

```python
capex: float | None = Field(
    default=None, gt=0,
    description=(
        "Total CAPEX (EUR). If omitted, computed from country + renovation_actions lookup."
    )
)
annual_maintenance_cost: float | None = Field(
    default=None, ge=0,
    description=(
        "Annual O&M cost (EUR/year). If omitted, computed from country + renovation_actions lookup."
    )
)
country: str | None = Field(
    default=None,
    description=(
        "Country name (one of 27 EU countries). Required when capex or "
        "annual_maintenance_cost is not provided explicitly."
    )
)
renovation_actions: list[RenovationAction] | None = Field(
    default=None,
    description=(
        "Renovation package. Required when capex or annual_maintenance_cost is not "
        "provided explicitly. Used to look up unit prices and O&M costs."
    )
)
```

Add a `model_validator` (after mode):
```python
@model_validator(mode="after")
def resolve_lookup_fields(self) -> RiskAssessmentRequest:
    needs_lookup = self.capex is None or self.annual_maintenance_cost is None
    if needs_lookup:
        if self.country is None:
            raise ValueError("country is required when capex or annual_maintenance_cost is not provided")
        if self.renovation_actions is None or len(self.renovation_actions) == 0:
            raise ValueError("renovation_actions is required when capex or annual_maintenance_cost is not provided")
    return self
```

### Step 4 — Update `services/risk_assessment.py`

At the top of `perform_risk_assessment()`, resolve any `None` values before calling
`get_kpi_results()`:

```python
from relife_financial.data.lookup import compute_capex, compute_opex

capex = request.capex
if capex is None:
    capex = compute_capex(request.country, request.renovation_actions)

opex = request.annual_maintenance_cost
if opex is None:
    opex = compute_opex(request.country, request.renovation_actions)
```

Also add `resolved_capex` and `resolved_opex` to the response `metadata` so the frontend can
show the user what values were actually used.

### Step 5 — Update `docs/RISK_ASSESSMENT_API_FRONTEND_CHANGELOG.md`

- Add `country` and `renovation_actions` to the request fields table
- Add a new example request: "Homeowner — let the API compute CAPEX/OPEX from renovation package"
- Add a note listing the 10 valid action names and the 27 supported countries
- Note that `capex` and `annual_maintenance_cost` are now optional (were required)

---

## Design decisions (confirmed / to confirm)

| # | Decision | Status | Choice |
|---|---|---|---|
| 1 | Material ambiguity | ✅ confirmed | Average across all materials for that country × action |
| 2 | Mixed overrides allowed | ✅ confirmed | Yes — user may supply `capex` but let OPEX be computed, or vice versa |
| 3 | Fixed + capacity cost for HVAC | ✅ confirmed | Both `Price[€]` and `Price[€/kW] × kW` must be summed |
| 4 | OPEX scaling | ✅ confirmed | Flat annual cost — no scaling by capacity (data doesn't support it) |
| 5 | Country field validation | ⚠️ to confirm | Enum of 27 vs. free string with normalisation |

> **Decision 5:** Using a strict `Literal` enum gives clear validation errors and enables
> autocomplete in frontend tools. Recommend: validate against the known 27-country list
> with a clear error message listing supported countries, but accept both "Czech Republic"
> and "Czechia" as aliases.

---

## Files to create / modify

| File | Change type |
|---|---|
| `src/relife_financial/data/lookup.py` | **Create** — data loading and lookup functions |
| `src/relife_financial/models/risk_assessment.py` | **Modify** — add `RenovationAction`, update `RiskAssessmentRequest` |
| `src/relife_financial/services/risk_assessment.py` | **Modify** — resolve capex/opex before calling engine |
| `docs/RISK_ASSESSMENT_API_FRONTEND_CHANGELOG.md` | **Modify** — document new optional fields + example |
| `tests/test_capex_opex_lookup.py` | **Create** — unit tests for `lookup.py` |
