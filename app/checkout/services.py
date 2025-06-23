import os
import json
import logging
from typing import Dict, Any, Optional, List
from decimal import Decimal
import httpx
from datetime import datetime
import paypalrestsdk
from .schemas import (
    CheckoutRequestSchema, 
    CheckoutResponseSchema, 
    PayPalOrderSchema,
    PaymentCaptureResponseSchema,
    WebhookEventSchema
)
from config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PayPalCommerceService:
    """PayPal Commerce Platform integration service"""
    
    def __init__(self):
        # Use configuration from settings
        self.client_id = settings.PAYPAL_CLIENT_ID
        self.client_secret = settings.PAYPAL_CLIENT_SECRET
        self.mode = settings.PAYPAL_MODE
        self.base_url = "https://api-m.sandbox.paypal.com" if self.mode == "sandbox" else "https://api-m.paypal.com"
        
        # Validate configuration
        if not settings.validate_paypal_config():
            logger.warning("PayPal configuration is incomplete. Please set PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET environment variables.")
        
        # Initialize PayPal SDK
        paypalrestsdk.configure({
            "mode": self.mode,
            "client_id": self.client_id,
            "client_secret": self.client_secret
        })
        
        self.access_token = None
        self.token_expires_at = None
    
    async def _get_access_token(self) -> str:
        """Get PayPal access token with caching"""
        if self.access_token and self.token_expires_at and datetime.utcnow() < self.token_expires_at:
            return self.access_token
        
        async with httpx.AsyncClient() as client:
            auth_response = await client.post(
                f"{self.base_url}/v1/oauth2/token",
                auth=(self.client_id, self.client_secret),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={"grant_type": "client_credentials"}
            )
            
            if auth_response.status_code != 200:
                raise Exception(f"Failed to get PayPal access token: {auth_response.text}")
            
            token_data = auth_response.json()
            self.access_token = token_data["access_token"]
            # Set expiration to 1 hour from now (with 5 minute buffer)
            self.token_expires_at = datetime.utcnow().replace(second=0, microsecond=0)
            self.token_expires_at = self.token_expires_at.replace(minute=self.token_expires_at.minute + 55)
            
            return self.access_token
    
    def _format_address(self, address) -> Dict[str, str]:
        """Format address for PayPal API"""
        return {
            "address_line_1": address.line1,
            "address_line_2": address.line2 or "",
            "admin_area_2": address.city,
            "admin_area_1": address.state,
            "postal_code": address.postal_code,
            "country_code": address.country_code
        }
    
    def _format_items(self, items: List) -> List[Dict[str, Any]]:
        """Format order items for PayPal API"""
        formatted_items = []
        for item in items:
            formatted_items.append({
                "name": item.name,
                "description": item.description or item.name,
                "quantity": str(item.quantity),
                "unit_amount": {
                    "currency_code": item.currency,
                    "value": str(item.unit_price)
                }
            })
        return formatted_items
    
    async def create_paypal_order(self, checkout_request: CheckoutRequestSchema) -> CheckoutResponseSchema:
        """Create PayPal order for checkout"""
        try:
            logger.info(f"Creating PayPal order for order_id: {checkout_request.order_id}")
            
            # Validate configuration
            if not settings.validate_paypal_config():
                return CheckoutResponseSchema(
                    success=False,
                    order_id=checkout_request.order_id,
                    status="failed",
                    message="PayPal configuration is incomplete. Please check your environment variables.",
                    error_code="CONFIG_ERROR",
                    timestamp=datetime.utcnow()
                )
            
            # Get access token
            access_token = await self._get_access_token()
            
            # Prepare purchase unit
            purchase_unit = {
                "reference_id": checkout_request.order_id,
                "description": f"Order {checkout_request.order_id}",
                "custom_id": checkout_request.order_id,
                "amount": {
                    "currency_code": checkout_request.currency,
                    "value": str(checkout_request.total_amount),
                    "breakdown": {
                        "item_total": {
                            "currency_code": checkout_request.currency,
                            "value": str(checkout_request.subtotal)
                        },
                        "tax_total": {
                            "currency_code": checkout_request.currency,
                            "value": str(checkout_request.tax_amount)
                        },
                        "shipping": {
                            "currency_code": checkout_request.currency,
                            "value": str(checkout_request.shipping_amount)
                        },
                        "discount": {
                            "currency_code": checkout_request.currency,
                            "value": str(checkout_request.discount_amount)
                        }
                    }
                },
                "items": self._format_items(checkout_request.items),
                "shipping": {
                    "name": {
                        "full_name": f"{checkout_request.customer.first_name} {checkout_request.customer.last_name}"
                    },
                    "address": self._format_address(checkout_request.shipping_address)
                }
            }
            
            # Prepare order data
            order_data = {
                "intent": "CAPTURE",
                "application_context": {
                    "return_url": f"{settings.FRONTEND_URL}/checkout/success",
                    "cancel_url": f"{settings.FRONTEND_URL}/checkout/cancel",
                    "brand_name": "Your Store Name",
                    "landing_page": "LOGIN",
                    "user_action": "PAY_NOW",
                    "shipping_preference": "SET_PROVIDED_ADDRESS"
                },
                "purchase_units": [purchase_unit]
            }
            
            # Create order via PayPal API
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/v2/checkout/orders",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                        "Prefer": "return=representation"
                    },
                    json=order_data
                )
                
                if response.status_code != 201:
                    error_data = response.json()
                    logger.error(f"PayPal order creation failed: {error_data}")
                    return CheckoutResponseSchema(
                        success=False,
                        order_id=checkout_request.order_id,
                        status="failed",
                        message=f"PayPal order creation failed: {error_data.get('message', 'Unknown error')}",
                        error_code=error_data.get('error', 'PAYPAL_ERROR'),
                        timestamp=datetime.utcnow()
                    )
                
                order_response = response.json()
                paypal_order_id = order_response["id"]
                
                logger.info(f"PayPal order created successfully: {paypal_order_id}")
                
                return CheckoutResponseSchema(
                    success=True,
                    order_id=checkout_request.order_id,
                    paypal_order_id=paypal_order_id,
                    status="created",
                    message="PayPal order created successfully",
                    timestamp=datetime.utcnow()
                )
                
        except Exception as e:
            logger.error(f"Error creating PayPal order: {str(e)}")
            return CheckoutResponseSchema(
                success=False,
                order_id=checkout_request.order_id,
                status="error",
                message=f"Error creating PayPal order: {str(e)}",
                error_code="INTERNAL_ERROR",
                timestamp=datetime.utcnow()
            )
    
    async def capture_payment(self, paypal_order_id: str, order_id: str) -> PaymentCaptureResponseSchema:
        """Capture PayPal payment"""
        try:
            logger.info(f"Capturing payment for PayPal order: {paypal_order_id}")
            
            # Validate configuration
            if not settings.validate_paypal_config():
                return PaymentCaptureResponseSchema(
                    success=False,
                    payment_id=paypal_order_id,
                    status="failed",
                    message="PayPal configuration is incomplete.",
                    timestamp=datetime.utcnow()
                )
            
            # Get access token
            access_token = await self._get_access_token()
            
            # Capture payment via PayPal API
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/v2/checkout/orders/{paypal_order_id}/capture",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                        "Prefer": "return=representation"
                    }
                )
                
                if response.status_code != 201:
                    error_data = response.json()
                    logger.error(f"PayPal payment capture failed: {error_data}")
                    return PaymentCaptureResponseSchema(
                        success=False,
                        payment_id=paypal_order_id,
                        status="failed",
                        message=f"Payment capture failed: {error_data.get('message', 'Unknown error')}",
                        timestamp=datetime.utcnow()
                    )
                
                capture_response = response.json()
                capture_id = capture_response["purchase_units"][0]["payments"]["captures"][0]["id"]
                capture_status = capture_response["status"]
                captured_amount = Decimal(capture_response["purchase_units"][0]["payments"]["captures"][0]["amount"]["value"])
                currency = capture_response["purchase_units"][0]["payments"]["captures"][0]["amount"]["currency_code"]
                
                logger.info(f"Payment captured successfully: {capture_id}")
                
                return PaymentCaptureResponseSchema(
                    success=True,
                    payment_id=paypal_order_id,
                    capture_id=capture_id,
                    status=capture_status,
                    amount=captured_amount,
                    currency=currency,
                    message="Payment captured successfully",
                    timestamp=datetime.utcnow()
                )
                
        except Exception as e:
            logger.error(f"Error capturing payment: {str(e)}")
            return PaymentCaptureResponseSchema(
                success=False,
                payment_id=paypal_order_id,
                status="error",
                message=f"Error capturing payment: {str(e)}",
                timestamp=datetime.utcnow()
            )
    
    async def get_order_details(self, paypal_order_id: str) -> Dict[str, Any]:
        """Get PayPal order details"""
        try:
            # Validate configuration
            if not settings.validate_paypal_config():
                return None
            
            access_token = await self._get_access_token()
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/v2/checkout/orders/{paypal_order_id}",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json"
                    }
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"Failed to get order details: {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error getting order details: {str(e)}")
            return None
    
    async def process_webhook(self, webhook_data: Dict[str, Any]) -> bool:
        """Process PayPal webhook events"""
        try:
            logger.info(f"Processing webhook event: {webhook_data.get('event_type')}")
            
            event_type = webhook_data.get("event_type")
            resource = webhook_data.get("resource", {})
            
            if event_type == "PAYMENT.CAPTURE.COMPLETED":
                # Payment was successfully captured
                capture_id = resource.get("id")
                status = resource.get("status")
                amount = resource.get("amount", {}).get("value")
                currency = resource.get("amount", {}).get("currency_code")
                
                logger.info(f"Payment capture completed: {capture_id}, Status: {status}, Amount: {amount} {currency}")
                
                # Here you would update your database with the payment status
                # await update_order_payment_status(capture_id, status)
                
            elif event_type == "PAYMENT.CAPTURE.DENIED":
                # Payment was denied
                capture_id = resource.get("id")
                logger.warning(f"Payment capture denied: {capture_id}")
                
                # Here you would update your database with the failed status
                # await update_order_payment_status(capture_id, "denied")
                
            elif event_type == "CHECKOUT.ORDER.APPROVED":
                # Order was approved by customer
                order_id = resource.get("id")
                logger.info(f"Order approved: {order_id}")
                
                # Here you would update your database with the approved status
                # await update_order_status(order_id, "approved")
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing webhook: {str(e)}")
            return False

class CheckoutService:
    """Main checkout service that orchestrates the payment process"""
    
    def __init__(self):
        self.paypal_service = PayPalCommerceService()
    
    async def process_checkout(self, checkout_request: CheckoutRequestSchema) -> CheckoutResponseSchema:
        """Process complete checkout flow"""
        try:
            logger.info(f"Processing checkout for order: {checkout_request.order_id}")
            
            # Validate request
            if not checkout_request.items:
                return CheckoutResponseSchema(
                    success=False,
                    order_id=checkout_request.order_id,
                    status="failed",
                    message="No items in order",
                    error_code="VALIDATION_ERROR",
                    timestamp=datetime.utcnow()
                )
            
            # Calculate total to verify
            calculated_total = (
                checkout_request.subtotal + 
                checkout_request.tax_amount + 
                checkout_request.shipping_amount - 
                checkout_request.discount_amount
            )
            
            if abs(calculated_total - checkout_request.total_amount) > Decimal('0.01'):
                return CheckoutResponseSchema(
                    success=False,
                    order_id=checkout_request.order_id,
                    status="failed",
                    message="Total amount calculation mismatch",
                    error_code="VALIDATION_ERROR",
                    timestamp=datetime.utcnow()
                )
            
            # Create PayPal order
            paypal_response = await self.paypal_service.create_paypal_order(checkout_request)
            
            if not paypal_response.success:
                return paypal_response
            
            # Here you would typically save the order to your database
            # await save_order_to_database(checkout_request, paypal_response.paypal_order_id)
            
            logger.info(f"Checkout processed successfully for order: {checkout_request.order_id}")
            return paypal_response
            
        except Exception as e:
            logger.error(f"Error processing checkout: {str(e)}")
            return CheckoutResponseSchema(
                success=False,
                order_id=checkout_request.order_id,
                status="error",
                message=f"Error processing checkout: {str(e)}",
                error_code="INTERNAL_ERROR",
                timestamp=datetime.utcnow()
            )
    
    async def capture_payment(self, paypal_order_id: str, order_id: str) -> PaymentCaptureResponseSchema:
        """Capture payment for an approved order"""
        try:
            logger.info(f"Capturing payment for order: {order_id}")
            
            capture_response = await self.paypal_service.capture_payment(paypal_order_id, order_id)
            
            if capture_response.success:
                # Here you would update your database with the captured payment
                # await update_order_payment_status(order_id, "captured", capture_response.capture_id)
                logger.info(f"Payment captured successfully for order: {order_id}")
            else:
                logger.error(f"Payment capture failed for order: {order_id}")
            
            return capture_response
            
        except Exception as e:
            logger.error(f"Error capturing payment: {str(e)}")
            return PaymentCaptureResponseSchema(
                success=False,
                payment_id=paypal_order_id,
                status="error",
                message=f"Error capturing payment: {str(e)}",
                timestamp=datetime.utcnow()
            ) 