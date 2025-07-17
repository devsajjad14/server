from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging
import requests
from .services import AdminService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize services
admin_service = AdminService()





class PaymentGatewayCredentials(BaseModel):
    gateway_name: str
    gateway_type: str
    display_name: str
    is_active: bool
    environment: str
    supports_digital_wallets: bool
    connection_status: str
    credentials: Dict[str, Any]
    sort_order: int = 0





@router.get("/payment-gateways")
async def get_payment_gateways():
    """
    Get all payment gateways and their credentials
    """
    try:
        logger.info("Fetching payment gateways")
        
        # Get gateways from admin service
        gateways = await admin_service.get_payment_gateways()
        
        return {
            "success": True,
            "gateways": gateways
        }
        
    except Exception as e:
        logger.error(f"Error fetching payment gateways: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@router.post("/payment-gateways")
async def save_payment_gateway(gateway: PaymentGatewayCredentials):
    """
    Save or update payment gateway credentials
    """
    try:
        logger.info(f"Saving payment gateway: {gateway.gateway_name}")
        
        # Save gateway using admin service
        result = await admin_service.save_payment_gateway(gateway.dict())
        
        if result["success"]:
            return {
                "success": True,
                "message": f"{gateway.display_name} credentials saved successfully",
                "gateway": result.get("gateway")
            }
        else:
            return {
                "success": False,
                "message": result.get("error", "Failed to save gateway credentials")
            }
            
    except Exception as e:
        logger.error(f"Error saving payment gateway: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@router.get("/payment-gateways/{gateway_name}")
async def get_payment_gateway(gateway_name: str):
    """
    Get specific payment gateway by name
    """
    try:
        logger.info(f"Fetching payment gateway: {gateway_name}")
        
        # Get gateway from admin service
        gateway = await admin_service.get_payment_gateway(gateway_name)
        
        if gateway:
            return {
                "success": True,
                "gateway": gateway
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Payment gateway '{gateway_name}' not found"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching payment gateway: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@router.get("/health")
async def admin_health_check():
    """
    Health check for admin endpoints
    """
    return {
        "success": True,
        "message": "Admin endpoints are healthy",
        "status": "operational"
    } 