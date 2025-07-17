from fastapi import APIRouter, HTTPException, Depends, Request, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional
import logging
import json
from datetime import datetime
from pydantic import ValidationError
import httpx
import stripe

from .schemas import (
    StripeCheckoutRequestSchema,
    StripeCheckoutResponseSchema,
    StripePaymentConfirmRequestSchema,
    StripePaymentConfirmResponseSchema,
    StripeRefundRequestSchema,
    StripeRefundResponseSchema,
    StripeWebhookEventSchema,
    StripeErrorSchema
)
from .services import StripeService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    tags=["Stripe Checkout"],
    prefix="",
    responses={404: {"description": "Not found"}},
)

# Global Stripe service instance (will be initialized with config)
stripe_service: Optional[StripeService] = None


def get_stripe_service() -> StripeService:
    """Dependency to get Stripe service instance"""
    if stripe_service is None:
        raise HTTPException(
            status_code=500,
            detail="Stripe service not initialized. Please check configuration."
        )
    return stripe_service


def initialize_stripe_service(api_key: str, webhook_secret: Optional[str] = None):
    """Initialize Stripe service with configuration"""
    global stripe_service
    try:
        stripe_service = StripeService(api_key, webhook_secret)
        logger.info("Stripe service initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Stripe service: {e}")
        raise


@router.post("/process-payment")
async def process_stripe_payment(request: Request):
    """
    Production-ready Stripe payment processing endpoint
    """
    try:
        # Parse the request body
        body = await request.json()
        
        # Extract payment config and checkout data
        payment_config = body.get('payment_config', {})
        checkout_data = {k: v for k, v in body.items() if k != 'payment_config'}
        
        logger.info(f"Processing Stripe payment for order: {checkout_data.get('order_id')}")
        
        # Validate payment configuration
        if not payment_config.get('api_key'):
            logger.error("No API key found in payment configuration")
            raise HTTPException(
                status_code=400,
                detail="Stripe API key is required in payment configuration"
            )
        
        # Extract payment method from the request
        payment_method_data = checkout_data.get('payment_method', {})
        card_number = payment_method_data.get('card_number', '')
        
        # Map test card numbers to their corresponding test tokens
        test_tokens = {
            '4242424242424242': 'tok_visa',
            '4000056655665556': 'tok_visa_debit',
            '5555555555554444': 'tok_mastercard',
            '2223003122003222': 'tok_mastercard_debit',
            '5200828282828210': 'tok_mastercard_prepaid',
            '5105105105105100': 'tok_mastercard',
            '378282246310005': 'tok_amex',
            '371449635398431': 'tok_amex',
            '6011111111111117': 'tok_discover',
            '3056930009020004': 'tok_diners',
            '3566002020360505': 'tok_jcb',
            '6200000000000005': 'tok_unionpay'
        }
        
        # Use direct HTTP requests for reliability
        async with httpx.AsyncClient() as client:
            # Determine if we should use test token or raw card data
            if card_number in test_tokens:
                # Use test token for known test cards
                test_token = test_tokens[card_number]
                logger.info(f"Using test token {test_token} for card number {card_number}")
                
                # Create PaymentMethod with test token
                payment_method_response = await client.post(
                    "https://api.stripe.com/v1/payment_methods",
                    data={
                        'type': 'card',
                        'card[token]': test_token,
                        'billing_details[name]': payment_method_data.get('name_on_card', 'Test User'),
                        'billing_details[email]': checkout_data.get('customer', {}).get('email', 'test@example.com')
                    },
                    headers={
                        "Authorization": f"Bearer {payment_config['api_key']}",
                        "Stripe-Version": "2024-12-18.acacia"
                    },
                    timeout=30.0
                )
            else:
                # For other cards, create PaymentMethod with raw data
                payment_method_response = await client.post(
                    "https://api.stripe.com/v1/payment_methods",
                    data={
                        'type': 'card',
                        'card[number]': card_number,
                        'card[exp_month]': payment_method_data.get('expiry_month'),
                        'card[exp_year]': payment_method_data.get('expiry_year'),
                        'card[cvc]': payment_method_data.get('cvc'),
                        'billing_details[name]': payment_method_data.get('name_on_card', 'Test User'),
                        'billing_details[email]': checkout_data.get('customer', {}).get('email', 'test@example.com')
                    },
                    headers={
                        "Authorization": f"Bearer {payment_config['api_key']}",
                        "Stripe-Version": "2024-12-18.acacia"
                    },
                    timeout=30.0
                )
            
            logger.info(f"PaymentMethod HTTP response status: {payment_method_response.status_code}")
            
            if payment_method_response.status_code != 200:
                error_text = payment_method_response.text
                logger.error(f"PaymentMethod creation failed: {error_text}")
                raise HTTPException(
                    status_code=400,
                    detail=f"PaymentMethod creation failed: {error_text}"
                )
            
            payment_method_data_response = payment_method_response.json()
            payment_method_id = payment_method_data_response['id']
            logger.info(f"PaymentMethod created successfully: {payment_method_id}")
            
            # Create PaymentIntent
            amount = int(float(checkout_data.get('total_amount', 0)))
            currency = checkout_data.get('currency', 'usd').lower()
            
            logger.info(f"Creating PaymentIntent with amount: {amount} {currency}")
            
            # Prepare PaymentIntent parameters
            payment_intent_params = {
                'amount': amount,
                'currency': currency,
                'description': f"Order {checkout_data.get('order_id', 'unknown')}",
                'payment_method': payment_method_id,
                'confirm': 'true',
                'metadata[order_id]': checkout_data.get('order_id', ''),
                'metadata[customer_email]': checkout_data.get('customer', {}).get('email', ''),
                'receipt_email': checkout_data.get('customer', {}).get('email', ''),
                # Configure automatic payment methods to prevent redirects
                'automatic_payment_methods[enabled]': 'true',
                'automatic_payment_methods[allow_redirects]': 'never'
            }
            
            payment_intent_response = await client.post(
                "https://api.stripe.com/v1/payment_intents",
                data=payment_intent_params,
                headers={
                    "Authorization": f"Bearer {payment_config['api_key']}",
                    "Stripe-Version": "2024-12-18.acacia"
                },
                timeout=30.0
            )
            
            logger.info(f"PaymentIntent HTTP response status: {payment_intent_response.status_code}")
            
            if payment_intent_response.status_code != 200:
                error_text = payment_intent_response.text
                logger.error(f"PaymentIntent creation failed: {error_text}")
                raise HTTPException(
                    status_code=400,
                    detail=f"PaymentIntent creation failed: {error_text}"
                )
            
            payment_intent_data = payment_intent_response.json()
            logger.info(f"PaymentIntent created successfully: {payment_intent_data['id']} with status: {payment_intent_data['status']}")
            
            # Prepare response
            response_data = {
                "success": True,
                "order_id": checkout_data.get('order_id'),
                "payment_intent": {
                    "id": payment_intent_data['id'],
                    "client_secret": payment_intent_data['client_secret'],
                    "status": payment_intent_data['status'],
                    "amount": payment_intent_data['amount'],
                    "currency": payment_intent_data['currency']
                },
                "payment_method": {
                    "id": payment_method_id,
                    "type": payment_method_data_response['type']
                },
                "status": payment_intent_data['status'],
                "message": "Payment processed successfully",
                "amount": payment_intent_data['amount'],
                "currency": payment_intent_data['currency'],
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Add next_action if present (for 3D Secure, etc.)
            if 'next_action' in payment_intent_data:
                response_data['requires_action'] = True
                response_data['next_action'] = payment_intent_data['next_action']
            
            return response_data
            
    except HTTPException:
        raise
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=f"Validation error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in process_stripe_payment: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/test-connection")
async def test_stripe_connection(request: Request):
    """
    Test Stripe connection and API key validity
    """
    try:
        body = await request.json()
        api_key = body.get('api_key')
        
        if not api_key:
            raise HTTPException(status_code=400, detail="API key is required")
        
        logger.info("Testing Stripe connection...")
        
        # Test connection by making a simple API call
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.stripe.com/v1/account",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Stripe-Version": "2024-12-18.acacia"
                },
                timeout=10.0
            )
            
            if response.status_code == 200:
                account_data = response.json()
                logger.info(f"Stripe connection successful for account: {account_data.get('id')}")
                return {
                    "success": True,
                    "message": "Stripe connection successful",
                    "account_id": account_data.get('id'),
                    "livemode": account_data.get('livemode', False),
                    "timestamp": datetime.utcnow().isoformat()
                }
            else:
                logger.error(f"Stripe connection failed: {response.text}")
                return {
                    "success": False,
                    "message": f"Stripe connection failed: {response.text}",
                    "timestamp": datetime.utcnow().isoformat()
                }
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing Stripe connection: {e}")
        raise HTTPException(status_code=500, detail=f"Error testing connection: {str(e)}")


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    stripe_service: StripeService = Depends(get_stripe_service)
):
    """
    Handle Stripe webhook events
    """
    try:
        # Get the raw body and signature
        body = await request.body()
        signature = request.headers.get('stripe-signature')
        
        if not signature:
            logger.error("No Stripe signature found in webhook request")
            raise HTTPException(status_code=400, detail="No signature found")
        
        # Verify webhook signature
        if not stripe_service.verify_webhook_signature(body, signature):
            logger.error("Invalid webhook signature")
            raise HTTPException(status_code=400, detail="Invalid signature")
        
        # Parse the event
        try:
            event_data = json.loads(body)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in webhook body: {e}")
            raise HTTPException(status_code=400, detail="Invalid JSON")
        
        event_type = event_data.get('type')
        logger.info(f"Processing webhook event: {event_type}")
        
        # Process the event in background
        background_tasks.add_task(process_webhook_event, event_data, stripe_service)
        
        return {"success": True, "message": "Webhook received"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        raise HTTPException(status_code=500, detail=f"Webhook processing error: {str(e)}")


async def process_webhook_event(event_data: Dict[str, Any], stripe_service: StripeService):
    """
    Process Stripe webhook events
    """
    try:
        event_type = event_data.get('type')
        
        if event_type == 'payment_intent.succeeded':
            await handle_payment_succeeded(event_data)
        elif event_type == 'payment_intent.payment_failed':
            await handle_payment_failed(event_data)
        elif event_type == 'payment_intent.canceled':
            await handle_payment_canceled(event_data)
        elif event_type == 'charge.refunded':
            await handle_payment_refunded(event_data)
        else:
            logger.info(f"Unhandled webhook event type: {event_type}")
            
    except Exception as e:
        logger.error(f"Error processing webhook event {event_data.get('type')}: {e}")


async def handle_payment_succeeded(event_data: Dict[str, Any]):
    """Handle successful payment"""
    try:
        payment_intent = event_data.get('data', {}).get('object', {})
        order_id = payment_intent.get('metadata', {}).get('order_id')
        
        logger.info(f"Payment succeeded for order: {order_id}")
        
        # Here you would typically:
        # 1. Update order status in your database
        # 2. Send confirmation email to customer
        # 3. Update inventory
        # 4. Trigger any post-payment workflows
        
    except Exception as e:
        logger.error(f"Error handling payment succeeded: {e}")


async def handle_payment_failed(event_data: Dict[str, Any]):
    """Handle failed payment"""
    try:
        payment_intent = event_data.get('data', {}).get('object', {})
        order_id = payment_intent.get('metadata', {}).get('order_id')
        last_payment_error = payment_intent.get('last_payment_error', {})
        
        logger.error(f"Payment failed for order: {order_id}")
        logger.error(f"Error: {last_payment_error.get('message', 'Unknown error')}")
        
        # Here you would typically:
        # 1. Update order status to failed
        # 2. Send failure notification to customer
        # 3. Log the failure for retry logic
        
    except Exception as e:
        logger.error(f"Error handling payment failed: {e}")


async def handle_payment_canceled(event_data: Dict[str, Any]):
    """Handle canceled payment"""
    try:
        payment_intent = event_data.get('data', {}).get('object', {})
        order_id = payment_intent.get('metadata', {}).get('order_id')
        
        logger.info(f"Payment canceled for order: {order_id}")
        
        # Here you would typically:
        # 1. Update order status to canceled
        # 2. Restore inventory
        # 3. Send cancellation notification
        
    except Exception as e:
        logger.error(f"Error handling payment canceled: {e}")


async def handle_payment_refunded(event_data: Dict[str, Any]):
    """Handle payment refund"""
    try:
        charge = event_data.get('data', {}).get('object', {})
        payment_intent_id = charge.get('payment_intent')
        
        logger.info(f"Payment refunded for PaymentIntent: {payment_intent_id}")
        
        # Here you would typically:
        # 1. Update order status to refunded
        # 2. Process refund in your system
        # 3. Send refund confirmation to customer
        
    except Exception as e:
        logger.error(f"Error handling payment refunded: {e}")


@router.post("/confirm-payment")
async def confirm_payment_intent(
    request: StripePaymentConfirmRequestSchema,
    stripe_service: StripeService = Depends(get_stripe_service)
):
    """
    Confirm a PaymentIntent (for 3D Secure, etc.)
    """
    try:
        return await stripe_service.confirm_payment_intent(request)
    except Exception as e:
        logger.error(f"Error confirming payment: {e}")
        raise HTTPException(status_code=500, detail=f"Payment confirmation error: {str(e)}")


@router.post("/refund-payment")
async def refund_payment(
    request: StripeRefundRequestSchema,
    stripe_service: StripeService = Depends(get_stripe_service)
):
    """
    Refund a payment
    """
    try:
        return await stripe_service.refund_payment(request)
    except Exception as e:
        logger.error(f"Error refunding payment: {e}")
        raise HTTPException(status_code=500, detail=f"Refund error: {str(e)}")


@router.get("/payment-intent/{payment_intent_id}")
async def get_payment_intent(
    payment_intent_id: str,
    stripe_service: StripeService = Depends(get_stripe_service)
):
    """
    Get PaymentIntent details
    """
    try:
        payment_intent = await stripe_service.get_payment_intent(payment_intent_id)
        if not payment_intent:
            raise HTTPException(status_code=404, detail="PaymentIntent not found")
        return payment_intent
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting PaymentIntent: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving PaymentIntent: {str(e)}") 