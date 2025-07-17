from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional
import logging
import json
from datetime import datetime

from .schemas import (
    SquareCheckoutRequestSchema,
    SquareCheckoutResponseSchema
)
from .services import SquareService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    tags=["Square Checkout"],
    prefix="",
    responses={404: {"description": "Not found"}},
)


@router.post("/process-payment", response_model=SquareCheckoutResponseSchema)
async def process_square_payment(request: Request):
    """
    Process payment using Square
    
    This endpoint processes a payment using Square's payment processing API.
    """
    try:
        logger.info("=== SQUARE PAYMENT PROCESSING START ===")
        
        # Parse request body
        body = await request.json()
        logger.info(f"Payment request received for order: {body.get('order_id', 'unknown')}")
        
        # Extract payment config from request body
        payment_config = body.get('payment_config', {})
        logger.info(f"Payment config received: {bool(payment_config)}")
        
        # Validate payment config
        if not payment_config:
            logger.error("Payment configuration is required in request body")
            raise HTTPException(
                status_code=400,
                detail="Payment configuration is required in request body"
            )
        
        # Extract Square credentials from payment config
        square_config = payment_config.get('square', {})
        application_id = square_config.get('application_id')
        access_token = square_config.get('access_token')
        location_id = square_config.get('location_id')
        environment = square_config.get('environment', 'sandbox')
        
        logger.info(f"Square config extracted: application_id={bool(application_id)}, access_token={bool(access_token)}, location_id={bool(location_id)}")
        
        if not application_id or not access_token or not location_id:
            logger.error("Missing Square credentials in payment config")
            raise HTTPException(
                status_code=400,
                detail="Missing Square credentials: application_id, access_token, and location_id are required"
            )
        
        logger.info(f"Using Square environment: {environment}")
        logger.info(f"Application ID: {application_id[:10]}...{application_id[-4:] if len(application_id) > 14 else '***'}")
        logger.info(f"Location ID: {location_id}")
        
        # Remove payment_config from body before validation to avoid schema conflicts
        checkout_data = {k: v for k, v in body.items() if k != 'payment_config'}
        
        # Validate request data
        try:
            checkout_request = SquareCheckoutRequestSchema(**checkout_data)
        except Exception as validation_error:
            logger.error(f"Request validation failed: {validation_error}")
            raise HTTPException(
                status_code=400,
                detail=f"Invalid request data: {str(validation_error)}"
            )
        
        # Create Square service instance
        square_service = SquareService(
            application_id=application_id,
            access_token=access_token,
            location_id=location_id,
            environment=environment
        )
        
        # Process payment using the simplified approach
        result = await square_service.create_payment(checkout_request, payment_config)
        
        logger.info(f"Payment processing result: {result.success}")
        if result.success:
            logger.info(f"Payment created successfully: {result.payment.id if result.payment else 'N/A'}")
        else:
            logger.error(f"Payment processing failed: {result.error.message if result.error else 'Unknown error'}")
        
        logger.info("=== SQUARE PAYMENT PROCESSING END ===")
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in payment processing: {str(e)}")
        logger.error(f"Full error details: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        ) 