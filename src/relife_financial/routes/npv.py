# File: routes/npv.py

from fastapi import APIRouter, Depends, HTTPException
from relife_financial.models.npv import NPVRequest, NPVResponse
from relife_financial.services.npv import calculate_npv
from relife_financial.auth.dependencies import get_authenticated_user_without_roles as get_current_user

router = APIRouter(
    prefix="/financial",
    tags=["financial"],
    responses={401: {"description": "Unauthorized"}},
)

@router.post("/npv", response_model=NPVResponse, summary="Calculate Net Present Value")
async def npv_endpoint(
    request: NPVRequest,
    #user = Depends(get_current_user),
):
    """
    Calculate the Net Present Value (NPV) for a series of cash flows.
    """

    try:
       npv_value = calculate_npv(
            cash_flows=request.cash_flows,
            discount_rate=request.discount_rate,
            energy_savings=request.energy_savings,
            initial_investment=request.initial_investment,
            lifetime=request.lifetime,
        )
       return NPVResponse(npv=npv_value, input=request)
    except Exception as e:
        # Return a 400 with the error message if something went wrong
        raise HTTPException(status_code=400, detail=str(e))

