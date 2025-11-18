
from fastapi import APIRouter, Depends, HTTPException
from relife_financial.models.ii import IIRequest, IIResponse
from relife_financial.services.ii import calculate_ii
from relife_financial.auth.dependencies import get_authenticated_user_without_roles as get_current_user

router = APIRouter(
    prefix="/financial",
    tags=["financial"],
    responses={401: {"description": "Unauthorized"}},
)

@router.post("/ii", response_model=IIResponse, summary="Calculate Initial Investment")
async def ii_endpoint(
    request: IIRequest,
    #user = Depends(get_current_user),
):
    """
    Calculate the II of Project.
    """

    try:
       ii_value = calculate_ii(
            capex=request.capex,
            interest_rate=request.interest_rate,
            loan_term=request.loan_term,
            loan_amount=request.loan_amount,
            subsidy=request.subsidy,
            

        )
       return IIResponse(ii=ii_value, input=request)
    except Exception as e:
        # Return a 400 with the error message if something went wrong
        raise HTTPException(status_code=400, detail=str(e))