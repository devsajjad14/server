from fastapi import APIRouter, HTTPException, Depends, Request, BackgroundTasks, Body
from fastapi.responses import JSONResponse
from typing import Dict, Any
import logging
from .schemas import (
    CheckoutRequestSchema,
    CheckoutResponseSchema,
    PayPalPaymentSchema,
    PaymentCaptureResponseSchema,
    WebhookEventSchema
)
from .services import CheckoutService, PayPalCommerceService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize services
checkout_service = CheckoutService()
paypal_service = PayPalCommerceService()

@router.post("/process-paypal", response_model=CheckoutResponseSchema)
async def process_paypal_checkout(
    request: CheckoutRequestSchema,
    background_tasks: BackgroundTasks
):
    """
    Process PayPal Commerce Platform checkout
    
    This endpoint receives order data from the frontend and creates a PayPal order.
    The user stays on your site throughout the process.
    """
    try:
        logger.info(f"Received raw checkout payload: {request.dict()}")
        logger.info(f"Received PayPal checkout request for order: {request.order_id}")
        
        # Validate payment method
        if request.payment_method.lower() != "paypal":
            raise HTTPException(
                status_code=400,
                detail="Invalid payment method. Only PayPal is supported."
            )
        
        # Process the checkout
        response = await checkout_service.process_checkout(request)
        
        if not response.success:
            logger.error(f"Checkout failed for order {request.order_id}: {response.message}")
            raise HTTPException(
                status_code=400,
                detail=response.message
            )
        
        logger.info(f"PayPal checkout processed successfully for order: {request.order_id}")
        
        # Add background task for order logging (optional)
        background_tasks.add_task(
            log_order_processing,
            request.order_id,
            response.paypal_order_id,
            "checkout_processed"
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in PayPal checkout: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error during checkout processing"
        )

@router.post("/capture-payment", response_model=PaymentCaptureResponseSchema)
async def capture_payment(
    payment_request: PayPalPaymentSchema,
    background_tasks: BackgroundTasks
):
    """
    Capture PayPal payment for an approved order
    
    This endpoint is called when the user approves the payment on PayPal.
    """
    try:
        logger.info(f"Capturing payment for order: {payment_request.order_id}")
        
        # Capture the payment
        response = await checkout_service.capture_payment(
            payment_request.payment_id,
            payment_request.order_id
        )
        
        if not response.success:
            logger.error(f"Payment capture failed for order {payment_request.order_id}: {response.message}")
            raise HTTPException(
                status_code=400,
                detail=response.message
            )
        
        logger.info(f"Payment captured successfully for order: {payment_request.order_id}")
        
        # Add background task for payment logging (optional)
        background_tasks.add_task(
            log_payment_capture,
            payment_request.order_id,
            response.capture_id,
            response.amount,
            response.currency
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in payment capture: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error during payment capture"
        )

@router.get("/order/{paypal_order_id}")
async def get_order_details(paypal_order_id: str):
    """
    Get PayPal order details
    
    This endpoint retrieves the current status and details of a PayPal order.
    """
    try:
        logger.info(f"Getting order details for PayPal order: {paypal_order_id}")
        
        order_details = await paypal_service.get_order_details(paypal_order_id)
        
        if not order_details:
            raise HTTPException(
                status_code=404,
                detail="Order not found"
            )
        
        return {
            "success": True,
            "order_details": order_details,
            "message": "Order details retrieved successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting order details: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while retrieving order details"
        )

@router.post("/webhook")
async def paypal_webhook(
    request: Request,
    background_tasks: BackgroundTasks
):
    """
    Handle PayPal webhook events
    
    This endpoint receives real-time notifications from PayPal about payment events.
    """
    try:
        # Get the raw body for webhook verification
        body = await request.body()
        headers = dict(request.headers)
        
        logger.info(f"Received PayPal webhook: {headers.get('paypal-transmission-id')}")
        
        # Verify webhook signature (recommended for production)
        # webhook_verified = await verify_webhook_signature(body, headers)
        # if not webhook_verified:
        #     logger.warning("Webhook signature verification failed")
        #     raise HTTPException(status_code=400, detail="Invalid webhook signature")
        
        # Parse webhook data
        webhook_data = await request.json()
        
        # Process webhook in background
        background_tasks.add_task(
            process_webhook_event,
            webhook_data
        )
        
        return {"success": True, "message": "Webhook received and processed"}
        
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while processing webhook"
        )

@router.get("/health")
async def health_check():
    """
    Health check endpoint for the checkout service
    """
    return {
        "status": "healthy",
        "service": "checkout",
        "paypal_mode": paypal_service.mode,
        "timestamp": "2024-01-01T00:00:00Z"
    }

# Background task functions
async def log_order_processing(order_id: str, paypal_order_id: str, status: str):
    """Background task to log order processing"""
    try:
        logger.info(f"Logging order processing: {order_id} -> {paypal_order_id} -> {status}")
        # Here you would log to your database or external logging service
        # await log_to_database(order_id, paypal_order_id, status)
    except Exception as e:
        logger.error(f"Error logging order processing: {str(e)}")

async def log_payment_capture(order_id: str, capture_id: str, amount: float, currency: str):
    """Background task to log payment capture"""
    try:
        logger.info(f"Logging payment capture: {order_id} -> {capture_id} -> {amount} {currency}")
        # Here you would log to your database or external logging service
        # await log_payment_to_database(order_id, capture_id, amount, currency)
    except Exception as e:
        logger.error(f"Error logging payment capture: {str(e)}")

async def process_webhook_event(webhook_data: Dict[str, Any]):
    """Background task to process webhook events"""
    try:
        logger.info(f"Processing webhook event: {webhook_data.get('event_type')}")
        
        # Process the webhook
        success = await paypal_service.process_webhook(webhook_data)
        
        if success:
            logger.info("Webhook processed successfully")
        else:
            logger.error("Webhook processing failed")
            
    except Exception as e:
        logger.error(f"Error processing webhook event: {str(e)}")

# Optional: Webhook signature verification function
async def verify_webhook_signature(body: bytes, headers: Dict[str, str]) -> bool:
    """
    Verify PayPal webhook signature
    
    This is a placeholder for webhook signature verification.
    In production, you should implement proper signature verification.
    """
    # For now, return True (you should implement proper verification)
    return True 