
from fastapi import APIRouter, Depends, HTTPException
from relife_financial.models.irr import IRRRequest, IRRResponse
from relife_financial.services.irr import calculate_irr
from relife_financial.auth.dependencies import get_authenticated_user_without_roles as get_current_user

router = APIRouter(
    prefix="/financial",
    tags=["financial"],
    responses={401: {"description": "Unauthorized"}},
)

@router.post("/irr", response_model=IRRResponse, summary="Calculate IRR")
async def irr_endpoint(
    request: IRRRequest,
    #user = Depends(get_current_user),
):
    """
    Calculate IRR of Project.
    """

    try:
     irr_value = calculate_irr(
        other_outflows=request.other_outflows,
        energy_savings=request.energy_savings,
        project_lifetime=request.project_lifetime,
        energy_mix=request.energy_mix,
        energy_prices=request.energy_prices,
        maintenance_cost=request.maintenance_cost,
        capex=request.capex,
        interest_rate=request.interest_rate,
        loan_term=request.loan_term,
        loan_amount=request.loan_amount,
        subsidy=request.subsidy,
    )
     return IRRResponse(irr=irr_value, input=request)
    except Exception as e:
        # Return a 400 with the error message if something went wrong
     raise HTTPException(status_code=400, detail=str(e))