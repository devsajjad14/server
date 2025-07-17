from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
import logging

from .services import SquareService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create router for test connection
router = APIRouter(
    tags=["Square Checkout"],
    prefix="",
    responses={404: {"description": "Not found"}},
)

class SquareTestRequest(BaseModel):
    application_id: str
    access_token: str
    location_id: str
    mode: str = "sandbox"

@router.post("/test-connection")
async def test_square_connection(
    request: SquareTestRequest
):
    """
    Test Square connection and credentials validity
    
    This endpoint tests the Square API connection using the provided credentials
    and verifies that the location ID exists in the account.
    """
    try:
        logger.info("=== SQUARE TEST CONNECTION START ===")
        logger.info(f"Testing connection for mode: {request.mode}")
        logger.info(f"Application ID: {request.application_id[:10]}...{request.application_id[-4:] if len(request.application_id) > 14 else '***'}")
        logger.info(f"Location ID: {request.location_id}")
        
        # Validate required fields
        if not request.application_id or not request.access_token or not request.location_id:
            logger.error("Missing required credentials")
            raise HTTPException(
                status_code=400,
                detail="Missing required credentials: application_id, access_token, and location_id are required"
            )
        
        # Create Square service instance
        square_service = SquareService(
            application_id=request.application_id,
            access_token=request.access_token,
            location_id=request.location_id,
            environment=request.mode
        )
        
        # Test connection
        result = await square_service.test_connection(request)
        
        logger.info(f"Test connection result: {result.success}")
        if not result.success:
            logger.error(f"Test connection failed: {result.error}")
        
        logger.info("=== SQUARE TEST CONNECTION END ===")
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in test connection: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        ) 