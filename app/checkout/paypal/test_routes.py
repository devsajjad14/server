from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
import logging

from app.checkout.paypal.services import PayPalCommerceService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create router for test connection
router = APIRouter(
    tags=["PayPal Checkout"],
    prefix="",
    responses={404: {"description": "Not found"}},
)

class PayPalTestRequest(BaseModel):
    client_id: str
    client_secret: str
    mode: str = "sandbox"

@router.post("/test-connection")
async def test_paypal_connection(request: PayPalTestRequest):
    """
    Test PayPal Commerce Platform connection with provided credentials
    """
    try:
        logger.info(f"Testing PayPal connection for mode: {request.mode}")
        
        # Create a temporary service instance for testing
        test_service = PayPalCommerceService()
        
        # Test the connection
        result = await test_service.test_connection(
            client_id=request.client_id,
            client_secret=request.client_secret,
            mode=request.mode
        )
        
        if result["success"]:
            logger.info("PayPal connection test successful")
            return {
                "success": True,
                "message": "PayPal connection test successful",
                "details": result.get("details", {})
            }
        else:
            logger.error(f"PayPal connection test failed: {result.get('error', 'Unknown error')}")
            return {
                "success": False,
                "message": result.get("error", "Connection test failed"),
                "details": result.get("details", {})
            }
            
    except Exception as e:
        logger.error(f"Error testing PayPal connection: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        ) 