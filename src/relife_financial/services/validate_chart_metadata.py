"""
Validation script specifically for cash flow chart metadata.

This script checks that the metadata sent to the frontend contains
all necessary fields and correct data to render the cash flow chart.
"""

import sys
from pathlib import Path
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.relife_financial.models.risk_assessment import (
    RiskAssessmentRequest,
    OutputLevel
)
from src.relife_financial.services.risk_assessment import perform_risk_assessment


def validate_cash_flow_metadata(viz_data: dict, request: RiskAssessmentRequest) -> dict:
    """
    Validate cash flow metadata against requirements.
    
    Returns:
        dict with 'valid': bool, 'errors': list, 'warnings': list
    """
    errors = []
    warnings = []
    
    # Required fields from the visualization function
    required_fields = [
        "years",
        "initial_investment",
        "annual_inflows",
        "annual_outflows",
        "annual_net_cash_flow",
        "cumulative_cash_flow",
        "breakeven_year",
        "loan_term"
    ]
    
    # Check all required fields exist
    for field in required_fields:
        if field not in viz_data:
            errors.append(f"Missing required field: '{field}'")
    
    if errors:
        return {"valid": False, "errors": errors, "warnings": warnings}
    
    # Validate array lengths
    expected_length = request.project_lifetime + 1  # Year 0 + operational years
    
    for field in ["years", "annual_inflows", "annual_outflows", "annual_net_cash_flow", "cumulative_cash_flow"]:
        if len(viz_data[field]) != expected_length:
            errors.append(
                f"'{field}' has wrong length: {len(viz_data[field])} (expected {expected_length})"
            )
    
    # Validate data types
    if not isinstance(viz_data["initial_investment"], (int, float)):
        errors.append("'initial_investment' must be a number")
    
    # Validate Year 0 conditions
    if viz_data["annual_inflows"][0] != 0.0:
        warnings.append(f"Year 0 should have no inflows, got {viz_data['annual_inflows'][0]}")
    
    if abs(viz_data["annual_outflows"][0] - viz_data["initial_investment"]) > 0.01:
        warnings.append(
            f"Year 0 outflow ({viz_data['annual_outflows'][0]}) doesn't match "
            f"initial_investment ({viz_data['initial_investment']})"
        )
    
    # Validate cumulative position at Year 0
    expected_year0_cumulative = -viz_data["initial_investment"]
    if abs(viz_data["cumulative_cash_flow"][0] - expected_year0_cumulative) > 0.01:
        warnings.append(
            f"Cumulative cash flow at Year 0 is {viz_data['cumulative_cash_flow'][0]}, "
            f"expected {expected_year0_cumulative}"
        )
    
    # Validate breakeven logic
    if viz_data["breakeven_year"] is not None:
        bey = viz_data["breakeven_year"]
        if bey < 0 or bey > request.project_lifetime:
            errors.append(f"Breakeven year {bey} is outside valid range [0, {request.project_lifetime}]")
        elif viz_data["cumulative_cash_flow"][bey] < 0:
            warnings.append(
                f"Cumulative cash flow at breakeven year {bey} is negative: "
                f"{viz_data['cumulative_cash_flow'][bey]}"
            )
    
    # Validate loan_term
    if viz_data["loan_term"] != request.loan_term:
        warnings.append(
            f"loan_term in metadata ({viz_data['loan_term']}) doesn't match "
            f"request ({request.loan_term})"
        )
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings
    }


def print_chart_structure(viz_data: dict):
    """Print the structure of chart data in a readable format."""
    print("\n" + "="*70)
    print("📊 CASH FLOW CHART DATA STRUCTURE")
    print("="*70)
    
    print("\n📐 Timeline:")
    print(f"   Years: {viz_data['years'][0]} → {viz_data['years'][-1]} ({len(viz_data['years'])} points)")
    
    print("\n💰 Initial Investment (Year 0):")
    print(f"   Out-of-pocket: €{viz_data['initial_investment']:,.2f}")
    
    print("\n📊 Arrays (length={}):", len(viz_data['years']))
    print(f"   ├─ annual_inflows: [0.0, {viz_data['annual_inflows'][1]:.2f}, ...]")
    print(f"   ├─ annual_outflows: [{viz_data['annual_outflows'][0]:.2f}, {viz_data['annual_outflows'][1]:.2f}, ...]")
    print(f"   ├─ annual_net_cash_flow: [{viz_data['annual_net_cash_flow'][0]:.2f}, {viz_data['annual_net_cash_flow'][1]:.2f}, ...]")
    print(f"   └─ cumulative_cash_flow: [{viz_data['cumulative_cash_flow'][0]:.2f}, {viz_data['cumulative_cash_flow'][1]:.2f}, ... , {viz_data['cumulative_cash_flow'][-1]:.2f}]")
    
    print("\n🎯 Milestones:")
    if viz_data['breakeven_year'] is not None:
        print(f"   ├─ Break-even: Year {viz_data['breakeven_year']}")
        print(f"   │   (Cumulative: €{viz_data['cumulative_cash_flow'][viz_data['breakeven_year']]:,.2f})")
    else:
        print(f"   ├─ Break-even: Never (project not profitable)")
    
    if viz_data['loan_term'] and viz_data['loan_term'] > 0:
        print(f"   └─ Loan paid off: Year {viz_data['loan_term']}")
    else:
        print(f"   └─ Loan: N/A")
    
    print("\n💵 Financial Summary:")
    total_inflows = sum(viz_data['annual_inflows'])
    total_outflows = sum(viz_data['annual_outflows'])
    final_position = viz_data['cumulative_cash_flow'][-1]
    
    print(f"   Total inflows: €{total_inflows:,.2f}")
    print(f"   Total outflows: €{total_outflows:,.2f}")
    print(f"   Final position: €{final_position:,.2f}")
    
    print("\n" + "="*70)


async def test_metadata_validation():
    """Run validation test on actual API output."""
    
    print("="*70)
    print("🧪 CASH FLOW CHART METADATA VALIDATION")
    print("="*70)
    
    # Test Case 1: With Loan
    print("\n" + "─"*70)
    print("Test Case 1: Scenario with Loan")
    print("─"*70)
    
    request_with_loan = RiskAssessmentRequest(
        capex=60000,
        annual_maintenance_cost=250,
        annual_energy_savings=27400,
        project_lifetime=20,
        loan_amount=20000,
        loan_term=15,
        output_level=OutputLevel.private
    )
    
    print("\n📋 Request:")
    print(f"   CAPEX: €{request_with_loan.capex:,}")
    print(f"   Loan: €{request_with_loan.loan_amount:,} over {request_with_loan.loan_term} years")
    print(f"   Lifetime: {request_with_loan.project_lifetime} years")
    
    print("\n⏳ Running simulation...")
    response = await perform_risk_assessment(request_with_loan)
    
    if "cash_flow_data" not in response.metadata:
        print("❌ ERROR: No cash_flow_data in metadata!")
        return
    
    viz_data = response.metadata["cash_flow_data"]
    
    # Validate
    result = validate_cash_flow_metadata(viz_data, request_with_loan)
    
    if result["valid"]:
        print("\n✅ VALIDATION PASSED")
    else:
        print("\n❌ VALIDATION FAILED")
        print("\nErrors:")
        for error in result["errors"]:
            print(f"   ❌ {error}")
    
    if result["warnings"]:
        print("\n⚠️  Warnings:")
        for warning in result["warnings"]:
            print(f"   ⚠️  {warning}")
    
    # Print structure
    print_chart_structure(viz_data)
    
    # Show JSON structure (what frontend will receive)
    print("\n📦 JSON Structure (Frontend will receive):")
    print("─"*70)
    print(json.dumps({
        "years": viz_data["years"][:3] + ["..."],
        "initial_investment": viz_data["initial_investment"],
        "annual_inflows": viz_data["annual_inflows"][:3] + ["..."],
        "annual_outflows": viz_data["annual_outflows"][:3] + ["..."],
        "annual_net_cash_flow": viz_data["annual_net_cash_flow"][:3] + ["..."],
        "cumulative_cash_flow": viz_data["cumulative_cash_flow"][:3] + ["..."],
        "breakeven_year": viz_data["breakeven_year"],
        "loan_term": viz_data["loan_term"]
    }, indent=2))
    
    # Test Case 2: Without Loan
    print("\n\n" + "─"*70)
    print("Test Case 2: Scenario without Loan")
    print("─"*70)
    
    request_no_loan = RiskAssessmentRequest(
        capex=60000,
        annual_maintenance_cost=250,
        annual_energy_savings=27400,
        project_lifetime=20,
        loan_amount=0,
        loan_term=0,
        output_level=OutputLevel.private
    )
    
    print("\n📋 Request:")
    print(f"   CAPEX: €{request_no_loan.capex:,}")
    print(f"   Loan: None")
    print(f"   Lifetime: {request_no_loan.project_lifetime} years")
    
    print("\n⏳ Running simulation...")
    response = await perform_risk_assessment(request_no_loan)
    
    viz_data = response.metadata["cash_flow_data"]
    
    # Validate
    result = validate_cash_flow_metadata(viz_data, request_no_loan)
    
    if result["valid"]:
        print("\n✅ VALIDATION PASSED")
    else:
        print("\n❌ VALIDATION FAILED")
        print("\nErrors:")
        for error in result["errors"]:
            print(f"   ❌ {error}")
    
    if result["warnings"]:
        print("\n⚠️  Warnings:")
        for warning in result["warnings"]:
            print(f"   ⚠️  {warning}")
    
    # Print structure
    print_chart_structure(viz_data)
    
    print("\n" + "="*70)
    print("✅ VALIDATION COMPLETE")
    print("="*70)
    print("\nThe metadata contains all necessary fields for the frontend to render:")
    print("   ✓ Timeline (years array)")
    print("   ✓ Bar chart data (inflows, outflows, net cash flow)")
    print("   ✓ Line chart data (cumulative cash flow)")
    print("   ✓ Milestone markers (breakeven, loan payoff)")
    print("   ✓ Initial investment (Year 0)")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_metadata_validation())
