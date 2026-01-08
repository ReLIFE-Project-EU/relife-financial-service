"""
Test script for private output with cash flow visualization.

This tests the complete private output flow including the
annual cash flow chart generation.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# Add Indicator Modules to path
indicator_modules_path = Path(__file__).parent.parent.parent.parent / "Indicator Modules"
if str(indicator_modules_path) not in sys.path:
    sys.path.insert(0, str(indicator_modules_path))

from src.relife_financial.models.risk_assessment import (
    RiskAssessmentRequest,
    OutputLevel
)
from src.relife_financial.services.risk_assessment import perform_risk_assessment


async def test_private_output_with_loan():
    """Test private output with loan scenario."""
    
    print("=" * 80)
    print("Testing Private Output with Loan Scenario")
    print("=" * 80)
    
    # Create request with loan
    request = RiskAssessmentRequest(
        capex=60000,
        annual_maintenance_cost=250,
        annual_energy_savings=27400,  # kWh
        project_lifetime=20,
        loan_amount=20000,
        loan_term=15,
        output_level=OutputLevel.private
    )
    
    print("\n📋 Request Parameters:")
    print(f"  CAPEX: €{request.capex:,}")
    print(f"  Annual Maintenance: €{request.annual_maintenance_cost:,}")
    print(f"  Annual Energy Savings: {request.annual_energy_savings:,} kWh")
    print(f"  Project Lifetime: {request.project_lifetime} years")
    print(f"  Loan Amount: €{request.loan_amount:,}")
    print(f"  Loan Term: {request.loan_term} years")
    print(f"  Output Level: {request.output_level}")
    
    # Perform risk assessment
    print("\n⏳ Running simulation (10,000 scenarios)...")
    response = await perform_risk_assessment(request)
    
    print("\n✅ Simulation complete!")
    
    # Display point forecasts
    print("\n📊 Point Forecasts (Median Values):")
    pf = response.point_forecasts
    print(f"  NPV: €{pf['NPV']:,.2f}")
    print(f"  IRR: {pf['IRR']:.2f}%")
    print(f"  ROI: {pf['ROI']:.2f}%")
    print(f"  Payback Period: {pf['PBP']:.1f} years")
    print(f"  Discounted Payback: {pf['DPP']:.1f} years")
    print(f"  Monthly Avg Savings: €{pf['MonthlyAvgSavings']:.2f}")
    print(f"  Success Rate: {pf['SuccessRate']:.1f}%")
    
    # Display metadata
    print("\n📝 Metadata:")
    for key, value in response.metadata.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.2f}")
        else:
            print(f"  {key}: {value}")
    
    # Check visualization
    print("\n🎨 Visualizations:")
    if response.visualizations:
        for key, viz_data in response.visualizations.items():
            if viz_data:
                size_kb = len(viz_data) / 1024
                print(f"  {key}: {size_kb:.1f} KB")
                
                # Save to file for inspection
                if viz_data.startswith("data:image/png;base64,"):
                    import base64
                    img_data = viz_data.split(",")[1]
                    output_path = Path(__file__).parent / f"test_{key}.png"
                    with open(output_path, "wb") as f:
                        f.write(base64.b64decode(img_data))
                    print(f"    Saved to: {output_path}")
            else:
                print(f"  {key}: Not generated")
    else:
        print("  No visualizations included")
    
    # Calculate response size
    import json
    response_json = response.model_dump_json()
    response_size_kb = len(response_json) / 1024
    print(f"\n📦 Total Response Size: {response_size_kb:.1f} KB")
    
    if response_size_kb > 10:
        print("  ⚠️ Warning: Response exceeds 10 KB target for private output")
    else:
        print("  ✅ Response size within target (~2 KB for point forecasts + metadata)")
    
    print("\n" + "=" * 80)


async def test_private_output_no_loan():
    """Test private output without loan."""
    
    print("\n" + "=" * 80)
    print("Testing Private Output without Loan")
    print("=" * 80)
    
    # Create request without loan
    request = RiskAssessmentRequest(
        capex=60000,
        annual_maintenance_cost=250,
        annual_energy_savings=27400,  # kWh
        project_lifetime=20,
        loan_amount=0,
        loan_term=0,
        output_level=OutputLevel.private
    )
    
    print("\n📋 Request Parameters:")
    print(f"  CAPEX: €{request.capex:,}")
    print(f"  Annual Maintenance: €{request.annual_maintenance_cost:,}")
    print(f"  Annual Energy Savings: {request.annual_energy_savings:,} kWh")
    print(f"  Project Lifetime: {request.project_lifetime} years")
    print(f"  Loan: None")
    print(f"  Output Level: {request.output_level}")
    
    # Perform risk assessment
    print("\n⏳ Running simulation (10,000 scenarios)...")
    response = await perform_risk_assessment(request)
    
    print("\n✅ Simulation complete!")
    
    # Display point forecasts
    print("\n📊 Point Forecasts (Median Values):")
    pf = response.point_forecasts
    print(f"  NPV: €{pf['NPV']:,.2f}")
    print(f"  IRR: {pf['IRR']:.2f}%")
    print(f"  ROI: {pf['ROI']:.2f}%")
    print(f"  Payback Period: {pf['PBP']:.1f} years")
    print(f"  Discounted Payback: {pf['DPP']:.1f} years")
    print(f"  Monthly Avg Savings: €{pf['MonthlyAvgSavings']:.2f}")
    print(f"  Success Rate: {pf['SuccessRate']:.1f}%")
    
    # Check visualization
    print("\n🎨 Visualizations:")
    if response.visualizations:
        for key, viz_data in response.visualizations.items():
            if viz_data:
                size_kb = len(viz_data) / 1024
                print(f"  {key}: {size_kb:.1f} KB")
                
                # Save to file for inspection
                if viz_data.startswith("data:image/png;base64,"):
                    import base64
                    img_data = viz_data.split(",")[1]
                    output_path = Path(__file__).parent / f"test_no_loan_{key}.png"
                    with open(output_path, "wb") as f:
                        f.write(base64.b64decode(img_data))
                    print(f"    Saved to: {output_path}")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    import asyncio
    
    # Run both tests
    asyncio.run(test_private_output_with_loan())
    asyncio.run(test_private_output_no_loan())
