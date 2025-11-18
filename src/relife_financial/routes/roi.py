
from fastapi import APIRouter, Depends, HTTPException
from relife_financial.models.roi import ROIRequest, ROIResponse
from relife_financial.services.roi import calculate_roi
from relife_financial.auth.dependencies import get_authenticated_user_without_roles as get_current_user

router = APIRouter(
    prefix="/financial",
    tags=["financial"],
    responses={401: {"description": "Unauthorized"}},
)

@router.post("/roi", response_model=ROIResponse, summary="Calculate ROI")
async def roi_endpoint(
    request: ROIRequest,
    #user = Depends(get_current_user),
):
    """
    Calculate ROI of Project.
    """

    try:
     roi_value = calculate_roi(
        capex=request.capex,
        interest_rate=request.interest_rate,
        loan_term=request.loan_term,
        loan_amount=request.loan_amount,
        subsidy=request.subsidy,
        energy_savings=request.energy_savings,
        energy_mix=request.energy_mix,
        energy_prices=request.energy_prices,
        maintenance_cost=request.maintenance_cost,
        other_outflows=request.other_outflows,
    )
     return ROIResponse(roi=roi_value, input=request)
    except Exception as e:
        # Return a 400 with the error message if something went wrong
     raise HTTPException(status_code=400, detail=str(e))