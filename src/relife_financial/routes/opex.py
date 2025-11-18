
from fastapi import APIRouter, Depends, HTTPException
from relife_financial.models.opex import OPEXRequest, OPEXResponse
from relife_financial.services.opex import calculate_opex
from relife_financial.auth.dependencies import get_authenticated_user_without_roles as get_current_user

router = APIRouter(
    prefix="/financial",
    tags=["financial"],
    responses={401: {"description": "Unauthorized"}},
)

@router.post("/opex", response_model=OPEXResponse, summary="Calculate Operational Expenses")
async def ii_endpoint(
    request: OPEXRequest,
    #user = Depends(get_current_user),
):
    """
    Calculate the OPEX of Project.
    """

    try:
       opex_value = calculate_opex(
            energy_mix=request.energy_mix,
            energy_prices=request.energy_prices,
            maintenance_cost=request.maintenance_cost,
            
  )
       return OPEXResponse(opex=opex_value, input=request)
    except Exception as e:
        # Return a 400 with the error message if something went wrong
        raise HTTPException(status_code=400, detail=str(e))