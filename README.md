# ReLIFE Financial Service

This service estimates the financial returns and risks of building renovation investments. Project partners can compare financing options using expected energy savings, renovation costs, and the investment period, and estimate property value after renovation.

## What it provides

- `POST /risk-assessment` compares financing schemes, including own funds, loans, energy service contracts, and crowdfunding. Monte Carlo simulations return net present value, internal rate of return, return on investment, and simple or discounted payback periods, with uncertainty statistics.
- Investment and annual maintenance costs can be supplied directly or calculated from country-specific reference data and the selected renovation works.
- `POST /arv` estimates after-renovation value and, when baseline energy consumption is supplied, the change in property value. The model was trained on Greek property data. Valuations for other countries also use this Greek-market model.

Output detail ranges from homeowner summaries to distributions for professional analysis.

See the [risk-assessment guide](docs/RISK_ASSESSMENT_API_FRONTEND_CHANGELOG.md) and [property-valuation guide](docs/ARV_API_FRONTEND_CHANGELOG.md) for inputs and outputs.

## Run locally

Requires Python 3.11 and `uv`. From the repository root:

```bash
uv sync --frozen
uv run --frozen run-service
```

Open [API documentation](http://localhost:9090/docs); `GET /health` checks availability. Set `API_HOST` and `API_PORT` to override `0.0.0.0:9090`.

Calculation requests require `SUPABASE_URL`, `SUPABASE_KEY`, `KEYCLOAK_CLIENT_ID`, and `KEYCLOAK_CLIENT_SECRET` in the environment, even without an authentication token. Keep credentials server-side. See [configuration](src/relife_financial/config/settings.py) for authentication defaults.

Run tests with `uv run --frozen pytest`. Licensed under [EUPL-1.2](LICENSE).
