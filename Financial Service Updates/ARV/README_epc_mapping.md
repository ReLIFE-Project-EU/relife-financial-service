# EPC Mapping Scripts

Two helper scripts for using the Greece price model with non-Greek EPC inputs.

## Files

### `test_model_energy_consumption_to_greek_epc.py`
Use this to map energy-consumption to EPC class.

Flow:
`energy consumption -> source-country EPC class -> Italy EPC class -> Greek EPC class -> Greece model`

Example:
```powershell
python .\test_model_energy_consumption_to_greek_epc.py `
  --target-country Austria `
  --energy-consumption 150 `
  --lat 37.981 `
  --lng 23.728 `
  --floor-area 110 `
  --construction-year 2002 `
  --floor-number 1 `
  --property-type-ui Apartment `
  --renovated-last-5-years true `
  --number-of-floors 4
```

### `test_model_country_epc_to_italy.py`
Use this with source-country EPC class. This is helpful to test the kwh -> EPC mapping and ensure the results align.

Flow:
`country EPC class -> Italy EPC class -> Greek EPC class -> Greece model`

Example:
```powershell
python .\test_model_country_epc_to_italy.py `
  --target-country Austria `
  --energy-class B `
  --lat 37.981 `
  --lng 23.728 `
  --floor-area 110 `
  --construction-year 2002 `
  --floor-number 1 `
  --property-type-ui Apartment `
  --renovated-last-5-years true `
  --number-of-floors 4
```


## Difference

- `test_model_country_epc_to_italy.py`: input is an EPC label like `A`, `B`, `C`, `A++`, etc.
- `test_model_energy_consumption_to_greek_epc.py`: input is a numeric consumption value like `150`.

Both scripts:
- always map through the Italy EPC scale first
- always convert the result to the Greek EPC scale
- always score with `lgb_model_greece.pkl`

## Notes

- Italy, Austria and Finland will be added to the script mapping. This is temporarily on hold until we resolve an API issue that transforms locations to lat,long. The following groupping will be used:
  GREECE_GROUP = ["SPAIN", "PORTUGAL", "ITALY_OLD", "CROATIA"]
  AUSTRIA_GROUP = ["AUSTRIA", "GERMANY", "CZECH_REP", "FRANCE", "BELGIUM_BRUSSELS", "BELGIUM_WALLONIA", "BELGIUM_FLANDERS", "NETHERLANDS", "BULGARIA", "SLOVAKIA", "ROMANIA"]
  FINLAND_GROUP = ["FINLAND", "DENMARK", "NORWAY", "LUXEMBOURG_HOUSES"]
- `--target-country` tells the script which national EPC system to interpret.
- Portugal and Czech Republic use `% of reference`, not `kWh/m²/year`, in the consumption-based script.
- The model pickle requires `lightgbm` to be installed:
  `pip install lightgbm`
