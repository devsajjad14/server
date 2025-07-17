from fastapi import APIRouter, HTTPException
import logging
from .services import KlarnaService, KlarnaTestConnectionRequestSchema, KlarnaTestConnectionResponseSchema

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Klarna Checkout"],
    prefix="",
    responses={404: {"description": "Not found"}},
)

@router.post("/test-connection", response_model=KlarnaTestConnectionResponseSchema)
async def test_klarna_connection(request: KlarnaTestConnectionRequestSchema):
    """
    Test Klarna API connection and credentials validity
    """
    try:
        logger.info("=== KLARNA TEST CONNECTION START ===")
        logger.info(f"Testing Klarna connection for environment: {request.environment}")

        if not (request.authorization or (request.username and request.password)):
            logger.error("Missing Klarna credentials or authorization header")
            raise HTTPException(status_code=400, detail="Missing Klarna credentials: provide either authorization or username/password")

        klarna_service = KlarnaService(
            username=request.username,
            password=request.password,
            environment=request.environment,
            authorization=request.authorization
        )
        result = await klarna_service.test_connection(request)
        logger.info(f"Test connection result: {result.success}")
        if not result.success:
            logger.error(f"Test connection failed: {result.message}")
        logger.info("=== KLARNA TEST CONNECTION END ===")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing Klarna connection: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Klarna test connection error: {str(e)}") 