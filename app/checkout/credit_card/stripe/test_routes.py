from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
import logging

from .services import StripeService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create router for test connection
router = APIRouter(
    tags=["Stripe Checkout"],
    prefix="",
    responses={404: {"description": "Not found"}},
)

class StripeTestRequest(BaseModel):
    api_key: str
    publishable_key: str = ""
    environment: str = "sandbox"

@router.post("/test-connection")
async def test_stripe_connection(
    request: StripeTestRequest
):
    """
    Test Stripe connection and API key validity
    
    This endpoint tests the Stripe connection using the provided API key.
    It attempts to make a simple API call to verify the credentials are valid.
    """
    try:
        # Debug: Print the entire request payload
        print("=== STRIPE TEST CONNECTION DEBUG ===")
        print(f"Request object: {request}")
        print(f"Request dict: {request.dict()}")
        print(f"API Key present: {bool(request.api_key)}")
        print(f"API Key length: {len(request.api_key) if request.api_key else 0}")
        print(f"API Key preview: {request.api_key[:10] + '...' if request.api_key else 'None'}")
        print(f"Publishable Key present: {bool(request.publishable_key)}")
        print(f"Environment: {request.environment}")
        print("=====================================")
        
        logger.info(f"Testing Stripe connection for environment: {request.environment}")
        
        # Validate request
        if not request.api_key:
            logger.error("No API key provided for connection test")
            raise HTTPException(
                status_code=400,
                detail="Stripe API key is required for connection test"
            )
        
        # Create a temporary service instance for testing
        test_service = StripeService(request.api_key)
        
        # Test the connection
        result = await test_service.test_connection(request.api_key)
        
        if result.get("success"):
            logger.info("Stripe connection test successful")
            return {
                "success": True,
                "message": "Stripe connection test successful",
                "details": result.get("details", {})
            }
        else:
            logger.error(f"Stripe connection test failed: {result.get('error', 'Unknown error')}")
            return {
                "success": False,
                "message": result.get("error", "Connection test failed"),
                "details": result.get("details", {})
            }
            
    except Exception as e:
        logger.error(f"Unexpected error testing Stripe connection: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        ) 