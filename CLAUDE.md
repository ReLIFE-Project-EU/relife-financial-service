# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**relife-financial** is a FastAPI-based financial service that provides financial indicator calculations (ROI, NPV, IRR, II, OPEX) for the ReLIFE project. It integrates with Supabase for database operations and Keycloak for authentication/authorization.

## Development Commands

### Running the Service

```bash
# Run the service (uses API_HOST and API_PORT env vars, defaults to 0.0.0.0:9090)
uv run run-service

# Or directly with uvicorn
uv run uvicorn relife_financial.app:app --host 0.0.0.0 --port 9090
```

### Testing

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_app.py

# Run with verbose output
uv run pytest -v

# Run with output capture disabled (see print statements)
uv run pytest -s
```

### Authentication Validation

```bash
# Validate authentication integration with Supabase
uv run validate-supabase --email <email> --auth-method supabase

# Validate with Keycloak user credentials
uv run validate-supabase --email <email> --auth-method keycloak-user

# Validate with Keycloak client credentials
uv run validate-supabase --email <email> --auth-method keycloak-client
```

### Package Management

```bash
# Install dependencies (uv handles virtualenv automatically)
uv sync

# Add new dependency
uv add <package-name>

# Add dev dependency
uv add --dev <package-name>
```

## Architecture

### Project Structure

```
src/relife_financial/
├── app.py                 # FastAPI app initialization, router registration
├── __init__.py            # Entry point with main() for uvicorn
├── auth/                  # Authentication layer
│   ├── keycloak.py        # Keycloak JWT validation, role fetching
│   └── dependencies.py    # FastAPI auth dependencies (user/service clients)
├── config/                # Configuration management
│   ├── settings.py        # Pydantic settings from env vars
│   └── logging.py         # Logging configuration
├── models/                # Pydantic models for request/response
│   ├── auth.py            # AuthenticatedUser, UniversalUser models
│   ├── npv.py, roi.py, irr.py, ii.py, opex.py  # Financial models
│   └── examples.py        # Example data models
├── routes/                # API endpoints
│   ├── auth.py            # /whoami endpoint
│   ├── health.py          # /health endpoint
│   ├── examples.py        # Example CRUD endpoints
│   └── npv.py, roi.py, irr.py, ii.py, opex.py  # Financial endpoints
├── services/              # Business logic for calculations
│   └── npv.py, roi.py, irr.py, ii.py, opex.py
└── scripts/
    └── validate_supabase.py  # CLI tool for auth testing
```

### Authentication System

The service implements a **dual authentication strategy** with automatic fallback:

1. **Primary**: Supabase authentication (for users synced to Supabase)
2. **Fallback**: Direct Keycloak JWT validation (for pure Keycloak users)

#### Key Dependencies

- `AuthenticatedUserDep`: Basic user authentication without roles
- `AuthenticatedUserWithRolesDep`: Authentication with Keycloak roles fetched
- `ServiceClientDep`: Supabase admin client (bypasses RLS, requires explicit permission checks)
- `UserClientDep`: Supabase user client (respects RLS, only works with Supabase-compatible tokens)

**Important**: Direct Keycloak tokens cannot use `UserClientDep` because they aren't compatible with Supabase RLS. Use `ServiceClientDep` with explicit role validation instead.

See `src/relife_financial/auth/dependencies.py` for detailed implementation.

### Financial Services

Each financial indicator follows a consistent pattern:

1. **Model** (`models/*.py`): Pydantic models for request/response validation
2. **Service** (`services/*.py`): Pure calculation logic using numpy/pandas
3. **Route** (`routes/*.py`): FastAPI endpoint connecting model to service

Example flow for ROI:
- Request → `ROIRequest` model validation
- Service → `calculate_roi()` performs financial calculation
- Response → `ROIResponse` with result + original input

All financial endpoints are under the `/financial` prefix.

### Configuration

All configuration is environment-driven via `Settings` class (see `config/settings.py`):

**Required Variables:**
- `SUPABASE_URL`: Supabase instance URL
- `SUPABASE_KEY`: Service role key (admin privileges, **never expose to clients**)
- `KEYCLOAK_CLIENT_ID`: Keycloak client ID
- `KEYCLOAK_CLIENT_SECRET`: Client secret for Keycloak

**Optional Variables:**
- `API_HOST`: Server host (default: `0.0.0.0`)
- `API_PORT`: Server port (default: `9090`)
- `KEYCLOAK_REALM_URL`: Keycloak realm URL (default: `https://relife-identity.test.ctic.es/realms/relife`)
- `ADMIN_ROLE_NAME`: Admin role name (default: `relife_admin`)
- `BUCKET_NAME`: Supabase storage bucket (default: `default_relife_bucket`)

### Testing Setup

Test configuration is in `tests/conftest.py`:
- Sets default environment variables for testing
- Provides `mock_settings` fixture for unit tests
- Auto-configures logging for all tests

Tests must set required env vars to avoid `Settings` validation errors.

## Key Implementation Notes

### Adding New Financial Indicators

1. Create model in `models/<indicator>.py`:
   ```python
   class IndicatorRequest(BaseModel):
       # Input fields

   class IndicatorResponse(BaseModel):
       result: float
       input: IndicatorRequest
   ```

2. Implement calculation in `services/<indicator>.py`:
   ```python
   def calculate_indicator(...) -> float:
       # Pure calculation logic
       return result
   ```

3. Create route in `routes/<indicator>.py`:
   ```python
   router = APIRouter(prefix="/financial", tags=["financial"])

   @router.post("/<indicator>", response_model=IndicatorResponse)
   async def indicator_endpoint(request: IndicatorRequest):
       result = calculate_indicator(**request.dict())
       return IndicatorResponse(result=result, input=request)
   ```

4. Register router in `app.py`:
   ```python
   from relife_financial.routes.<indicator> import router as indicator_router
   app.include_router(indicator_router)
   ```

### Authentication in Endpoints

Most endpoints are currently **not** enforcing authentication (commented out). To require authentication:

```python
from relife_financial.auth.dependencies import get_authenticated_user_without_roles as get_current_user

@router.post("/endpoint")
async def endpoint(
    request: RequestModel,
    user = Depends(get_current_user),  # Uncomment to require auth
):
    pass
```

For role-based access:
```python
from relife_financial.auth.dependencies import get_authenticated_user_with_roles

@router.post("/admin-endpoint")
async def admin_endpoint(
    user = Depends(get_authenticated_user_with_roles),
):
    if "relife_admin" not in user.keycloak_roles:
        raise HTTPException(status_code=403, detail="Admin access required")
```

## Technology Stack

- **Python 3.11+**: Required minimum version
- **FastAPI**: Web framework with auto-generated OpenAPI docs at `/docs`
- **Uvicorn**: ASGI server
- **Supabase**: Backend-as-a-Service (database + storage)
- **Keycloak**: Identity and access management
- **Pydantic**: Data validation via type hints
- **NumPy/Pandas**: Financial calculations
- **Pytest**: Async testing framework
- **uv**: Fast Python package manager
