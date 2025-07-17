from fastapi import APIRouter, HTTPException
from .test_routes import router as test_router
from .services import KlarnaService, KlarnaSessionRequestSchema, KlarnaSessionResponseSchema

router = APIRouter(
    tags=["Klarna Checkout"],
    prefix="",
    responses={404: {"description": "Not found"}},
)
router.include_router(test_router, prefix="")

@router.post("/session", response_model=KlarnaSessionResponseSchema)
async def create_klarna_session(request: KlarnaSessionRequestSchema):
    """
    Create a Klarna payment session for the frontend widget
    """
    try:
        klarna_service = KlarnaService()
        result = await klarna_service.create_session(request)
        if not result.success:
            raise HTTPException(status_code=400, detail=result.message)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Klarna session creation error: {str(e)}") 