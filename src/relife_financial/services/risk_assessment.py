"""
Risk Assessment Service - Business Logic Layer

Orchestrates the Monte Carlo simulation for all requested financing schemes
and builds the response based on the output_level.
"""

import math
import sys
from pathlib import Path
from typing import Any, Dict

# Add Indicator Modules to path
indicator_modules_path = Path(__file__).parent.parent / "Indicator Modules"
if str(indicator_modules_path) not in sys.path:
    sys.path.insert(0, str(indicator_modules_path))

from simulation_engine import (
    SchemeConfigurationError,
    FinancialSimulationError,
    get_kpi_results,
)

from ..data.lookup import compute_capex, compute_opex
from ..models.risk_assessment import (
    OutputLevel,
    RiskAssessmentRequest,
    RiskAssessmentResponse,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _sanitize_for_json(value: Any) -> Any:
    """Recursively replace NaN/Inf values with None for safe JSON serialisation."""
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, dict):
        return {k: _sanitize_for_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize_for_json(v) for v in value]
    return value


def _filter_by_output_level(scheme_data: Dict[str, Any], output_level: OutputLevel) -> Dict[str, Any]:
    """
    Return the subset of scheme_data appropriate for the requested output_level.

    private:       summary + cashflow_distributions
    professional:  summary + cashflow_distributions + kpi_histograms
    public:        same as professional
    complete:      everything from get_kpi_results
    """
    filtered: Dict[str, Any] = {
        "scheme_id":     scheme_data["scheme_id"],
        "scheme_family": scheme_data["scheme_family"],
        "summary":       scheme_data["summary"],
        # Cash-flow fan charts included for all output levels (needed for timeline viz)
        "cashflow_distributions": scheme_data["cashflow_distributions"],
    }

    if output_level in (OutputLevel.professional, OutputLevel.public, OutputLevel.complete):
        filtered["kpi_histograms"] = scheme_data["kpi_histograms"]

    return filtered


# ─────────────────────────────────────────────────────────────────────────────
# Main service function
# ─────────────────────────────────────────────────────────────────────────────

async def perform_risk_assessment(request: RiskAssessmentRequest) -> RiskAssessmentResponse:
    """
    Perform multi-scheme Monte Carlo risk assessment.

    Steps:
    1. Convert Pydantic scheme models to (scheme_type, details) tuples.
    2. Run get_kpi_results() for all schemes in a single simulation pass.
    3. Filter the raw output based on output_level.
    4. Return a structured RiskAssessmentResponse.

    Raises
    ------
    ValueError
        For invalid scheme configuration or bad input parameters.
    RuntimeError
        If the Monte Carlo simulation itself fails.
    """
    # ── Resolve CAPEX / OPEX (lookup if not explicitly provided) ───────────────
    capex_from_lookup = request.capex is None
    opex_from_lookup = request.annual_maintenance_cost is None

    if capex_from_lookup:
        capex = compute_capex(request.country, request.renovation_actions)
    else:
        capex = request.capex

    if opex_from_lookup:
        opex = compute_opex(request.country, request.renovation_actions)
    else:
        opex = request.annual_maintenance_cost if request.annual_maintenance_cost is not None else 0.0

    # ── Convert scheme models to engine tuples ────────────────────────────────
    schemes = []
    for s in request.schemes:
        details = s.model_dump(exclude={"scheme_type", "scheme_family"})
        schemes.append((s.scheme_type, details))

    # ── Run simulation ────────────────────────────────────────────────────────
    try:
        raw_results = get_kpi_results(
            capex=capex,
            annual_energy_savings=request.annual_energy_savings,
            annual_maintenace_cost=opex,
            project_lifetime=request.project_lifetime,
            schemes=schemes,
            n_sims=10000,
            seed=42,
        )
    except SchemeConfigurationError as exc:
        raise ValueError(str(exc)) from exc
    except FinancialSimulationError as exc:
        raise RuntimeError(str(exc)) from exc
    except Exception as exc:
        raise RuntimeError(f"Simulation failed: {exc}") from exc

    # ── Build filtered output per scheme ─────────────────────────────────────
    results: Dict[str, Any] = {}
    for scheme_type, data in raw_results.items():
        filtered = _filter_by_output_level(data, request.output_level)

        # Restrict KPI percentiles to requested indicators
        if "summary" in filtered and "percentiles" in filtered["summary"]:
            requested = set(request.indicators)
            # Always keep total_repayment if present (useful for debt schemes)
            keep = requested | {"total_repayment"}
            filtered["summary"]["percentiles"] = {
                k: v for k, v in filtered["summary"]["percentiles"].items()
                if k in keep
            }

        results[scheme_type] = _sanitize_for_json(filtered)

    # ── Build metadata ────────────────────────────────────────────────────────
    metadata = _sanitize_for_json({
        "capex":                    capex,
        "capex_from_lookup":        capex_from_lookup,
        "annual_energy_savings":    request.annual_energy_savings,
        "annual_maintenance_cost":  opex,
        "opex_from_lookup":         opex_from_lookup,
        "project_lifetime":         request.project_lifetime,
        "n_schemes":                len(results),
        "scheme_types":             list(results.keys()),
        "output_level":             request.output_level.value,
        "indicators_requested":     request.indicators,
        "n_sims":                   10000,
    })

    return RiskAssessmentResponse(results=results, metadata=metadata)
