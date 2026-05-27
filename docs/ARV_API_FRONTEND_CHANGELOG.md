# ARV API — Frontend Integration Guide

## What Changed

The ARV endpoint (`POST /arv`) has been updated to accept energy consumption values directly instead of EPC labels. The API now resolves the EPC class internally and — when a pre-renovation value is supplied — returns a full before/after comparison with uplift figures in a single response.

---

## Breaking Changes Summary

| # | What | Before | After |
|---|------|--------|-------|
| 1 | Input field removed | `energy_class` (EPC enum string, e.g. `"Β+"`) | **Removed** |
| 2 | Input field renamed | `energy_consumption` | `energy_consumption_after` |
| 3 | Input field added | — | `energy_consumption_before` *(optional)* |
| 4 | Input field added | — | `target_country` *(required)* |
| 5 | Response field renamed | `energy_class` | moved into `after.greek_epc_class` |
| 6 | Response restructured | flat object | nested `after` / `before` / `uplift` objects |

---

## Request

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `lat` | float | ✅ | Latitude (decimal degrees, −90 to 90) |
| `lng` | float | ✅ | Longitude (decimal degrees, −180 to 180) |
| `floor_area` | float > 0 | ✅ | Usable floor area in m² |
| `construction_year` | int | ✅ | Year of original construction (1800–2030) |
| `floor_number` | int or null | — | Floor level (0 = ground). `null` for detached houses |
| `number_of_floors` | int ≥ 1 | ✅ | Total floors in the building |
| `property_type` | string enum | ✅ | See property type values below |
| `target_country` | string | ✅ | Country whose EPC scale applies. See supported values below |
| `energy_consumption_after` | float > 0 | ✅ | Post-renovation energy consumption |
| `energy_consumption_before` | float > 0 | — | Pre-renovation energy consumption. **Provide to get before/after comparison and uplift** |
| `renovated_last_5_years` | bool | — | Default: `true` |

### `property_type` values

`"Apartment"`, `"Villa"`, `"Detached House"`, `"Maisonette"`, `"Studio / Bedsit"`, `"Loft"`, `"Building"`, `"Apartment Complex"`, `"Other"`

### `target_country` values

`"Greece"`, `"Italy"`, `"Croatia"`, `"Spain"`, `"Portugal"`, `"Czech Republic"`, `"Germany"`, `"France"`, `"Austria"`, `"Netherlands"`, `"Belgium Brussels"`, `"Belgium Wallonia"`, `"Belgium Flanders"`, `"Luxembourg Flats"`, `"Luxembourg Houses"`, `"Denmark"`, `"Norway"`, `"Finland"`, `"Bulgaria"`, `"Romania"`, `"Slovakia"`

Common aliases are also accepted (e.g. `"hellas"`, `"brussels"`, `"flanders"`, `"czechia"`).

### `energy_consumption_after` / `energy_consumption_before` units

- **All countries except Portugal and Czech Republic**: kWh/m²/year
- **Portugal and Czech Republic**: % of reference consumption

---

## Example Requests

### Post-renovation value only

```json
{
    "lat": 37.981,
    "lng": 23.728,
    "floor_area": 85.0,
    "construction_year": 1985,
    "floor_number": 2,
    "number_of_floors": 5,
    "property_type": "Apartment",
    "target_country": "Italy",
    "energy_consumption_after": 85.0,
    "renovated_last_5_years": true
}
```

### With before/after comparison

```json
{
    "lat": 37.981,
    "lng": 23.728,
    "floor_area": 85.0,
    "construction_year": 1985,
    "floor_number": 2,
    "number_of_floors": 5,
    "property_type": "Apartment",
    "target_country": "Italy",
    "energy_consumption_before": 220.0,
    "energy_consumption_after": 85.0,
    "renovated_last_5_years": true
}
```

---

## Response

### Structure

```
{
  "after":   ARVValueSnapshot   — always present
  "before":  ARVValueSnapshot   — present only when energy_consumption_before was sent
  "uplift":  ARVUplift          — present only when energy_consumption_before was sent
  "floor_area": float
  "metadata": object
}
```

### `ARVValueSnapshot` fields

| Field | Type | Description |
|-------|------|-------------|
| `price_per_sqm` | float | Predicted price per m² (€/m²) |
| `total_price` | float | `price_per_sqm × floor_area` (€) |
| `greek_epc_class` | string | Resolved Greek EPC class used by the model (e.g. `"Ε"`, `"Η"`, `"Α+"`) |
| `epc_resolution` | object | EPC chain: `target_country`, `source_epc_class`, `italy_epc_class`, `greek_epc_class` |

### `ARVUplift` fields

| Field | Type | Description |
|-------|------|-------------|
| `price_increase` | float | Absolute increase in total property value (€). Can be negative |
| `price_increase_pct` | float | Percentage increase. Can be negative |

---

## Example Responses

### Post-renovation value only (`energy_consumption_before` not provided)

```json
{
    "after": {
        "price_per_sqm": 1235.50,
        "total_price": 105017.50,
        "greek_epc_class": "Ε",
        "epc_resolution": {
            "target_country": "Italy",
            "source_epc_class": "E",
            "italy_epc_class": "E",
            "greek_epc_class": "Ε"
        }
    },
    "before": null,
    "uplift": null,
    "floor_area": 85.0,
    "metadata": {
        "model_file": "lgb_model_greece.pkl",
        "prediction_timestamp": "2026-05-27T14:30:00.123456",
        "building_age": 41,
        "energy_consumption_unit": "kWh/m²/year"
    }
}
```

### With before/after comparison

```json
{
    "after": {
        "price_per_sqm": 1235.50,
        "total_price": 105017.50,
        "greek_epc_class": "Ε",
        "epc_resolution": {
            "target_country": "Italy",
            "source_epc_class": "E",
            "italy_epc_class": "E",
            "greek_epc_class": "Ε"
        }
    },
    "before": {
        "price_per_sqm": 980.00,
        "total_price": 83300.00,
        "greek_epc_class": "Η",
        "epc_resolution": {
            "target_country": "Italy",
            "source_epc_class": "G",
            "italy_epc_class": "G",
            "greek_epc_class": "Η"
        }
    },
    "uplift": {
        "price_increase": 21717.50,
        "price_increase_pct": 26.07
    },
    "floor_area": 85.0,
    "metadata": {
        "model_file": "lgb_model_greece.pkl",
        "prediction_timestamp": "2026-05-27T14:30:00.123456",
        "building_age": 41,
        "energy_consumption_unit": "kWh/m²/year"
    }
}
```

---

## Migration Checklist

- [ ] Remove `energy_class` from the request payload
- [ ] Rename `energy_consumption` → `energy_consumption_after`
- [ ] Add `target_country` to the request payload
- [ ] Optionally add `energy_consumption_before` to request to receive uplift data
- [ ] Update response parsing: replace flat `price_per_sqm` / `total_price` / `energy_class` reads with `after.price_per_sqm` / `after.total_price` / `after.greek_epc_class`
- [ ] Handle `before` and `uplift` being `null` when only post-renovation consumption is sent
