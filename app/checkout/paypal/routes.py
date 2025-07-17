from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from typing import Dict, Any
import logging
from app.checkout.schemas import (
    CheckoutRequestSchema,
    CheckoutResponseSchema,
    WebhookEventSchema
)
from app.checkout.services import CheckoutService
from app.checkout.paypal.services import PayPalCommerceService
from app.checkout.paypal.test_routes import router as test_router

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["PayPal Checkout"],
    prefix="",
    responses={404: {"description": "Not found"}},
)

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
    """
    try:
        logger.info(f"Received raw checkout payload: {request.dict()}")
        logger.info(f"Received PayPal checkout request for order: {request.order_id}")
        if request.payment_method.lower() != "paypal":
            raise HTTPException(
                status_code=400,
                detail="Invalid payment method. Only PayPal is supported."
            )
        response = await checkout_service.process_checkout(request, request.payment_config)
        if not response.success:
            logger.error(f"Checkout failed for order {request.order_id}: {response.message}")
            raise HTTPException(
                status_code=400,
                detail=response.message
            )
        logger.info(f"PayPal checkout processed successfully for order: {request.order_id}")
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

@router.post("/webhook")
async def paypal_webhook(
    request: Request,
    background_tasks: BackgroundTasks
):
    """
    Handle PayPal webhook events
    """
    try:
        body = await request.body()
        headers = dict(request.headers)
        logger.info(f"Received PayPal webhook: {headers.get('paypal-transmission-id')}")
        webhook_data = await request.json()
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

# Include the PayPal test connection router
router.include_router(test_router, prefix="")

async def log_order_processing(order_id: str, paypal_order_id: str, status: str):
    try:
        logger.info(f"Logging order processing: {order_id} -> {paypal_order_id} -> {status}")
    except Exception as e:
        logger.error(f"Error logging order processing: {str(e)}")

async def process_webhook_event(webhook_data: Dict[str, Any]):
    try:
        logger.info(f"Processing webhook event: {webhook_data.get('event_type')}")
        success = await paypal_service.process_webhook(webhook_data)
        if success:
            logger.info("Webhook processed successfully")
        else:
            logger.error("Webhook processing failed")
    except Exception as e:
        logger.error(f"Error processing webhook event: {str(e)}") 