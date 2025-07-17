import os
import json
import logging
import asyncio
from typing import Dict, Any, Optional, List, Tuple
from decimal import Decimal
import stripe
from datetime import datetime, timedelta
import httpx
from .schemas import (
    StripeCheckoutRequestSchema,
    StripeCheckoutResponseSchema,
    StripePaymentIntentSchema,
    StripePaymentMethodResponseSchema,
    StripeCustomerSchema,
    StripePaymentConfirmRequestSchema,
    StripePaymentConfirmResponseSchema,
    StripeRefundRequestSchema,
    StripeRefundResponseSchema,
    StripeErrorSchema,
    StripePaymentIntentStatus,
    PaymentMethodType
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StripeService:
    """Production-ready Stripe payment processing service"""
    
    def __init__(self, api_key: str, webhook_secret: Optional[str] = None):
        """
        Initialize Stripe service with API key and webhook secret
        
        Args:
            api_key: Stripe secret key
            webhook_secret: Webhook endpoint secret for signature verification
        """
        if not api_key:
            raise ValueError("Stripe API key is required")
        
        self.api_key = api_key
        self.webhook_secret = webhook_secret
        
        # Configure Stripe with API key
        stripe.api_key = api_key
        
        # Set API version for consistency
        stripe.api_version = '2024-12-18.acacia'
        
        # Configure logging for Stripe
        stripe.log = 'info'
        
        logger.info(f"Stripe service initialized with API version: {stripe.api_version}")
        logger.info(f"API key configured: {api_key[:10]}...{api_key[-4:] if len(api_key) > 14 else '***'}")
    
    async def create_payment_intent(
        self, 
        request: StripeCheckoutRequestSchema,
        payment_config: Dict[str, Any]
    ) -> StripeCheckoutResponseSchema:
        """
        Create a Stripe PaymentIntent for processing the payment
        
        Args:
            request: Checkout request with order and payment details
            payment_config: Payment gateway configuration
            
        Returns:
            StripeCheckoutResponseSchema with payment intent details
        """
        try:
            logger.info(f"Creating PaymentIntent for order: {request.order_id}")
            
            # Create or retrieve customer
            customer = await self._get_or_create_customer(request.customer)
            logger.info(f"Customer created/found: {customer.id}")
            
            # Create payment method
            payment_method = await self._create_payment_method(request.payment_method, customer.id)
            logger.info(f"PaymentMethod created: {payment_method.id}")
            
            # Prepare PaymentIntent parameters
            payment_intent_params = {
                'amount': int(request.total_amount),  # Convert to cents
                'currency': request.currency.lower(),
                'customer': customer.id,
                'payment_method': payment_method.id,
                'confirmation_method': 'manual',
                'confirm': True,
                'description': f"Order {request.order_id} - {len(request.items)} items",
                'receipt_email': request.customer.email,
                'metadata[order_id]': request.order_id,
                'metadata[customer_email]': request.customer.email,
                'metadata[items_count]': str(len(request.items)),
                # Configure automatic payment methods to prevent redirects
                'automatic_payment_methods[enabled]': 'true',
                'automatic_payment_methods[allow_redirects]': 'never'
            }
            
            # Add shipping address if provided
            if request.shipping_address:
                payment_intent_params.update({
                    'shipping[name]': f"{request.customer.first_name} {request.customer.last_name}",
                    'shipping[address][line1]': request.shipping_address.line1,
                    'shipping[address][line2]': request.shipping_address.line2 or '',
                    'shipping[address][city]': request.shipping_address.city,
                    'shipping[address][state]': request.shipping_address.state,
                    'shipping[address][postal_code]': request.shipping_address.postal_code,
                    'shipping[address][country]': request.shipping_address.country_code.upper()
                })
            
            # Add return_url if provided
            if request.return_url:
                payment_intent_params['return_url'] = request.return_url
            
            # Create PaymentIntent using direct HTTP request for reliability
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.stripe.com/v1/payment_intents",
                    data=payment_intent_params,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Stripe-Version": "2024-12-18.acacia"
                    },
                    timeout=30.0
                )
                
                if response.status_code != 200:
                    error_text = response.text
                    logger.error(f"PaymentIntent creation failed: {error_text}")
                    return self._create_error_response(
                        request.order_id,
                        f"Failed to create payment intent: {error_text}",
                        "payment_intent_creation_failed"
                    )
                
                payment_intent_data = response.json()
                logger.info(f"PaymentIntent created: {payment_intent_data['id']} with status: {payment_intent_data['status']}")
                
                # Create response schema
                payment_intent = StripePaymentIntentSchema(
                    id=payment_intent_data['id'],
                    client_secret=payment_intent_data['client_secret'],
                    status=payment_intent_data['status'],
                    amount=payment_intent_data['amount'],
                    currency=payment_intent_data['currency'],
                    created=datetime.fromtimestamp(payment_intent_data['created']),
                    metadata=payment_intent_data.get('metadata', {}),
                    next_action=payment_intent_data.get('next_action'),
                    payment_method_types=payment_intent_data.get('payment_method_types', [])
                )
                
                # Create customer schema
                customer_schema = StripeCustomerSchema(
                    id=customer.id,
                    email=customer.email,
                    name=f"{request.customer.first_name} {request.customer.last_name}",
                    phone=request.customer.phone,
                    created=datetime.fromtimestamp(customer.created),
                    metadata=customer.metadata
                )
                
                # Create payment method schema
                payment_method_schema = StripePaymentMethodResponseSchema(
                    id=payment_method.id,
                    type=payment_method.type,
                    card=payment_method.card,
                    billing_details=payment_method.billing_details,
                    created=datetime.fromtimestamp(payment_method.created),
                    customer=customer.id
                )
                
                return StripeCheckoutResponseSchema(
                    success=True,
                    payment_intent=payment_intent,
                    payment_method=payment_method_schema,
                    customer=customer_schema,
                    order_id=request.order_id,
                    amount=payment_intent_data['amount'],
                    currency=payment_intent_data['currency'],
                    status=payment_intent_data['status'],
                    message="Payment intent created successfully",
                    requires_action=payment_intent_data['status'] == 'requires_action',
                    next_action=payment_intent_data.get('next_action'),
                    timestamp=datetime.utcnow()
                )
                
        except Exception as e:
            logger.error(f"Error creating payment intent: {e}")
            return self._create_error_response(
                request.order_id,
                f"Error creating payment intent: {str(e)}",
                "payment_intent_error"
            )
    
    async def confirm_payment_intent(
        self, 
        request: StripePaymentConfirmRequestSchema
    ) -> StripePaymentConfirmResponseSchema:
        """
        Confirm a PaymentIntent (for 3D Secure, etc.)
        
        Args:
            request: Payment confirmation request
            
        Returns:
            StripePaymentConfirmResponseSchema with confirmation details
        """
        try:
            logger.info(f"Confirming PaymentIntent: {request.payment_intent_id}")
            
            # Prepare confirmation parameters
            confirm_params = {}
            
            if request.payment_method_id:
                confirm_params['payment_method'] = request.payment_method_id
            
            if request.return_url:
                confirm_params['return_url'] = request.return_url
            
            # Confirm PaymentIntent using direct HTTP request
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://api.stripe.com/v1/payment_intents/{request.payment_intent_id}/confirm",
                    data=confirm_params,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Stripe-Version": "2024-12-18.acacia"
                    },
                    timeout=30.0
                )
                
                if response.status_code != 200:
                    error_text = response.text
                    logger.error(f"PaymentIntent confirmation failed: {error_text}")
                    return StripePaymentConfirmResponseSchema(
                        success=False,
                        status="failed",
                        message=f"Payment confirmation failed: {error_text}",
                        error=error_text,
                        timestamp=datetime.utcnow()
                    )
                
                payment_intent_data = response.json()
                logger.info(f"PaymentIntent confirmed: {payment_intent_data['id']} with status: {payment_intent_data['status']}")
                
                # Create payment intent schema
                payment_intent = StripePaymentIntentSchema(
                    id=payment_intent_data['id'],
                    client_secret=payment_intent_data['client_secret'],
                    status=payment_intent_data['status'],
                    amount=payment_intent_data['amount'],
                    currency=payment_intent_data['currency'],
                    created=datetime.fromtimestamp(payment_intent_data['created']),
                    metadata=payment_intent_data.get('metadata', {}),
                    next_action=payment_intent_data.get('next_action'),
                    payment_method_types=payment_intent_data.get('payment_method_types', [])
                )
                
                return StripePaymentConfirmResponseSchema(
                    success=True,
                    payment_intent=payment_intent,
                    status=payment_intent_data['status'],
                    message="Payment confirmed successfully",
                    timestamp=datetime.utcnow()
                )
                
        except Exception as e:
            logger.error(f"Error confirming payment intent: {e}")
            return StripePaymentConfirmResponseSchema(
                success=False,
                status="failed",
                message=f"Error confirming payment: {str(e)}",
                error=str(e),
                timestamp=datetime.utcnow()
            )
    
    async def refund_payment(
        self, 
        request: StripeRefundRequestSchema
    ) -> StripeRefundResponseSchema:
        """
        Refund a payment
        
        Args:
            request: Refund request details
            
        Returns:
            StripeRefundResponseSchema with refund details
        """
        try:
            logger.info(f"Processing refund for PaymentIntent: {request.payment_intent_id}")
            
            # Get the PaymentIntent to find the charge
            payment_intent = await self.get_payment_intent(request.payment_intent_id)
            if not payment_intent:
                return StripeRefundResponseSchema(
                    success=False,
                    status="failed",
                    message="PaymentIntent not found",
                    error="PaymentIntent not found",
                    timestamp=datetime.utcnow()
                )
            
            # Prepare refund parameters
            refund_params = {}
            
            if request.amount:
                refund_params['amount'] = request.amount
            
            if request.reason:
                refund_params['reason'] = request.reason
            
            if request.metadata:
                for key, value in request.metadata.items():
                    refund_params[f'metadata[{key}]'] = value
            
            # Create refund using direct HTTP request
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.stripe.com/v1/refunds",
                    data=refund_params,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Stripe-Version": "2024-12-18.acacia"
                    },
                    timeout=30.0
                )
                
                if response.status_code != 200:
                    error_text = response.text
                    logger.error(f"Refund creation failed: {error_text}")
                    return StripeRefundResponseSchema(
                        success=False,
                        status="failed",
                        message=f"Refund failed: {error_text}",
                        error=error_text,
                        timestamp=datetime.utcnow()
                    )
                
                refund_data = response.json()
                logger.info(f"Refund created: {refund_data['id']} with status: {refund_data['status']}")
                
                return StripeRefundResponseSchema(
                    success=True,
                    refund_id=refund_data['id'],
                    amount=refund_data['amount'],
                    status=refund_data['status'],
                    message="Refund processed successfully",
                    timestamp=datetime.utcnow()
                )
                
        except Exception as e:
            logger.error(f"Error processing refund: {e}")
            return StripeRefundResponseSchema(
                success=False,
                status="failed",
                message=f"Error processing refund: {str(e)}",
                error=str(e),
                timestamp=datetime.utcnow()
            )
    
    async def get_payment_intent(self, payment_intent_id: str) -> Optional[StripePaymentIntentSchema]:
        """
        Retrieve a PaymentIntent by ID
        
        Args:
            payment_intent_id: The PaymentIntent ID
            
        Returns:
            StripePaymentIntentSchema or None if not found
        """
        try:
            logger.info(f"Retrieving PaymentIntent: {payment_intent_id}")
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://api.stripe.com/v1/payment_intents/{payment_intent_id}",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Stripe-Version": "2024-12-18.acacia"
                    },
                    timeout=10.0
                )
                
                if response.status_code != 200:
                    logger.error(f"Failed to retrieve PaymentIntent: {response.text}")
                    return None
                
                payment_intent_data = response.json()
                
                return StripePaymentIntentSchema(
                    id=payment_intent_data['id'],
                    client_secret=payment_intent_data['client_secret'],
                    status=payment_intent_data['status'],
                    amount=payment_intent_data['amount'],
                    currency=payment_intent_data['currency'],
                    created=datetime.fromtimestamp(payment_intent_data['created']),
                    metadata=payment_intent_data.get('metadata', {}),
                    next_action=payment_intent_data.get('next_action'),
                    payment_method_types=payment_intent_data.get('payment_method_types', [])
                )
                
        except Exception as e:
            logger.error(f"Error retrieving PaymentIntent: {e}")
            return None
    
    async def _get_or_create_customer(self, customer_data) -> stripe.Customer:
        """
        Get or create a Stripe customer
        
        Args:
            customer_data: Customer information
            
        Returns:
            Stripe Customer object
        """
        try:
            # Try to find existing customer by email
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.stripe.com/v1/customers",
                    params={'email': customer_data.email},
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Stripe-Version": "2024-12-18.acacia"
                    },
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    customers_data = response.json()
                    if customers_data['data']:
                        # Return existing customer
                        customer_info = customers_data['data'][0]
                        logger.info(f"Found existing customer: {customer_info['id']}")
                        
                        # Create mock customer object
                        class MockCustomer:
                            def __init__(self, customer_data):
                                self.id = customer_data['id']
                                self.email = customer_data['email']
                                self.name = customer_data.get('name')
                                self.phone = customer_data.get('phone')
                                self.created = customer_data['created']
                                self.metadata = customer_data.get('metadata', {})
                        
                        return MockCustomer(customer_info)
                
                # Create new customer
                customer_params = {
                    'email': customer_data.email,
                    'name': f"{customer_data.first_name} {customer_data.last_name}",
                    'phone': customer_data.phone,
                    'metadata[first_name]': customer_data.first_name,
                    'metadata[last_name]': customer_data.last_name
                }
                
                response = await client.post(
                    "https://api.stripe.com/v1/customers",
                    data=customer_params,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Stripe-Version": "2024-12-18.acacia"
                    },
                    timeout=10.0
                )
                
                if response.status_code != 200:
                    error_text = response.text
                    logger.error(f"Customer creation failed: {error_text}")
                    raise Exception(f"Failed to create customer: {error_text}")
                
                customer_info = response.json()
                logger.info(f"Created new customer: {customer_info['id']}")
                
                # Create mock customer object
                class MockCustomer:
                    def __init__(self, customer_data):
                        self.id = customer_data['id']
                        self.email = customer_data['email']
                        self.name = customer_data.get('name')
                        self.phone = customer_data.get('phone')
                        self.created = customer_data['created']
                        self.metadata = customer_data.get('metadata', {})
                
                return MockCustomer(customer_info)
                
        except Exception as e:
            logger.error(f"Error in _get_or_create_customer: {e}")
            raise
    
    async def _create_payment_method(self, payment_method_data, customer_id: str):
        """
        Create a Stripe PaymentMethod
        
        Args:
            payment_method_data: Payment method information
            customer_id: Customer ID to attach the payment method to
            
        Returns:
            Stripe PaymentMethod object
        """
        try:
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
            
            card_number = payment_method_data.card_number
            
            async with httpx.AsyncClient() as client:
                if card_number in test_tokens:
                    # Use test token for known test cards
                    test_token = test_tokens[card_number]
                    logger.info(f"Using test token {test_token} for card number {card_number}")
                    
                    payment_method_params = {
                        'type': 'card',
                        'card[token]': test_token,
                        'billing_details[name]': payment_method_data.name_on_card,
                        'billing_details[email]': payment_method_data.email if hasattr(payment_method_data, 'email') else 'test@example.com'
                    }
                else:
                    # Use raw card data for other cards
                    payment_method_params = {
                        'type': 'card',
                        'card[number]': card_number,
                        'card[exp_month]': payment_method_data.expiry_month,
                        'card[exp_year]': payment_method_data.expiry_year,
                        'card[cvc]': payment_method_data.cvc,
                        'billing_details[name]': payment_method_data.name_on_card,
                        'billing_details[email]': payment_method_data.email if hasattr(payment_method_data, 'email') else 'test@example.com'
                    }
                
                response = await client.post(
                    "https://api.stripe.com/v1/payment_methods",
                    data=payment_method_params,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Stripe-Version": "2024-12-18.acacia"
                    },
                    timeout=30.0
                )
                
                if response.status_code != 200:
                    error_text = response.text
                    logger.error(f"PaymentMethod creation failed: {error_text}")
                    raise Exception(f"Failed to create payment method: {error_text}")
                
                payment_method_info = response.json()
                logger.info(f"PaymentMethod created: {payment_method_info['id']}")
                
                # Attach payment method to customer
                attach_response = await client.post(
                    f"https://api.stripe.com/v1/payment_methods/{payment_method_info['id']}/attach",
                    data={'customer': customer_id},
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Stripe-Version": "2024-12-18.acacia"
                    },
                    timeout=10.0
                )
                
                if attach_response.status_code != 200:
                    logger.warning(f"Failed to attach payment method to customer: {attach_response.text}")
                
                # Create mock payment method object
                class MockPaymentMethod:
                    def __init__(self, payment_method_data):
                        self.id = payment_method_data['id']
                        self.type = payment_method_data['type']
                        self.card = payment_method_data.get('card')
                        self.billing_details = payment_method_data.get('billing_details')
                        self.created = payment_method_data['created']
                        self.customer = payment_method_data.get('customer')
                
                return MockPaymentMethod(payment_method_info)
                
        except Exception as e:
            logger.error(f"Error in _create_payment_method: {e}")
            raise
    
    def _create_error_response(
        self, 
        order_id: str, 
        message: str, 
        error_code: Optional[str] = None,
        error_type: Optional[str] = None
    ) -> StripeCheckoutResponseSchema:
        """
        Create an error response
        
        Args:
            order_id: Order ID
            message: Error message
            error_code: Error code
            error_type: Error type
            
        Returns:
            StripeCheckoutResponseSchema with error details
        """
        return StripeCheckoutResponseSchema(
            success=False,
            order_id=order_id,
            amount=0,
            currency="usd",
            status="failed",
            message=message,
            error=message,
            timestamp=datetime.utcnow()
        )
    
    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """
        Verify Stripe webhook signature
        
        Args:
            payload: Raw webhook payload
            signature: Stripe signature header
            
        Returns:
            True if signature is valid, False otherwise
        """
        try:
            if not self.webhook_secret:
                logger.warning("No webhook secret configured, skipping signature verification")
                return True
            
            # Use Stripe's webhook signature verification
            event = stripe.Webhook.construct_event(
                payload, signature, self.webhook_secret
            )
            
            logger.info(f"Webhook signature verified for event: {event.get('type')}")
            return True
            
        except ValueError as e:
            logger.error(f"Invalid webhook payload: {e}")
            return False
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid webhook signature: {e}")
            return False
        except Exception as e:
            logger.error(f"Error verifying webhook signature: {e}")
            return False
    
    async def test_connection(self, api_key: str) -> Dict[str, Any]:
        """
        Test Stripe connection and API key validity
        
        Args:
            api_key: Stripe API key to test
            
        Returns:
            Dictionary with connection test results
        """
        try:
            logger.info("Testing Stripe connection...")
            
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
                    
        except Exception as e:
            logger.error(f"Error testing Stripe connection: {e}")
            return {
                "success": False,
                "message": f"Error testing connection: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            } 