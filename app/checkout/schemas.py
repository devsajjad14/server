from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
from decimal import Decimal
from datetime import datetime

class AddressSchema(BaseModel):
    """Address information for shipping/billing"""
    line1: str = Field(..., description="Street address line 1")
    line2: Optional[str] = Field(None, description="Street address line 2")
    city: str = Field(..., description="City")
    state: str = Field(..., description="State or province")
    postal_code: str = Field(..., description="Postal/ZIP code")
    country_code: str = Field(..., description="Two-letter country code (e.g., US)")

class CustomerSchema(BaseModel):
    """Customer information"""
    email: EmailStr = Field(..., description="Customer email address")
    first_name: str = Field(..., description="Customer first name")
    last_name: str = Field(..., description="Customer last name")
    phone: Optional[str] = Field(None, description="Customer phone number")

class OrderItemSchema(BaseModel):
    """Individual order item"""
    product_id: str = Field(..., description="Product identifier")
    name: str = Field(..., description="Product name")
    quantity: int = Field(..., gt=0, description="Quantity ordered")
    unit_price: Decimal = Field(..., gt=0, description="Unit price")
    currency: str = Field(default="USD", description="Currency code")
    description: Optional[str] = Field(None, description="Product description")

class CheckoutRequestSchema(BaseModel):
    """Complete checkout request from frontend"""
    order_id: str = Field(..., description="Unique order identifier")
    customer: CustomerSchema = Field(..., description="Customer information")
    items: List[OrderItemSchema] = Field(..., description="Order items")
    shipping_address: AddressSchema = Field(..., description="Shipping address")
    billing_address: Optional[AddressSchema] = Field(None, description="Billing address (optional, uses shipping if not provided)")
    subtotal: Decimal = Field(..., gt=0, description="Order subtotal")
    tax_amount: Decimal = Field(default=0, ge=0, description="Tax amount")
    shipping_amount: Decimal = Field(default=0, ge=0, description="Shipping cost")
    discount_amount: Decimal = Field(default=0, ge=0, description="Discount amount")
    total_amount: Decimal = Field(..., gt=0, description="Total order amount")
    currency: str = Field(default="USD", description="Currency code")
    payment_method: str = Field(default="paypal", description="Payment method")
    notes: Optional[str] = Field(None, description="Order notes")

class PayPalOrderSchema(BaseModel):
    """PayPal order creation request"""
    intent: str = Field(default="CAPTURE", description="Payment intent")
    application_context: Dict[str, Any] = Field(
        default_factory=lambda: {
            "return_url": "http://localhost:3000/checkout/success",
            "cancel_url": "http://localhost:3000/checkout/cancel",
            "brand_name": "Your Store Name",
            "landing_page": "LOGIN",
            "user_action": "PAY_NOW",
            "shipping_preference": "SET_PROVIDED_ADDRESS"
        },
        description="PayPal application context"
    )
    purchase_units: List[Dict[str, Any]] = Field(..., description="Purchase units")

class PayPalPaymentSchema(BaseModel):
    """PayPal payment capture request"""
    payment_id: str = Field(..., description="PayPal payment ID")
    order_id: str = Field(..., description="Your order ID")

class CheckoutResponseSchema(BaseModel):
    """Checkout response to frontend"""
    success: bool = Field(..., description="Operation success status")
    order_id: str = Field(..., description="Order identifier")
    paypal_order_id: Optional[str] = Field(None, description="PayPal order ID")
    payment_id: Optional[str] = Field(None, description="PayPal payment ID")
    status: str = Field(..., description="Payment status")
    redirect_url: Optional[str] = Field(None, description="PayPal redirect URL (if needed)")
    message: str = Field(..., description="Response message")
    error_code: Optional[str] = Field(None, description="Error code if failed")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")

class PaymentCaptureResponseSchema(BaseModel):
    """Payment capture response"""
    success: bool = Field(..., description="Capture success status")
    payment_id: str = Field(..., description="PayPal payment ID")
    capture_id: Optional[str] = Field(None, description="PayPal capture ID")
    status: str = Field(..., description="Capture status")
    amount: Optional[Decimal] = Field(None, description="Captured amount")
    currency: Optional[str] = Field(None, description="Currency code")
    message: str = Field(..., description="Response message")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")

class WebhookEventSchema(BaseModel):
    """PayPal webhook event"""
    id: str = Field(..., description="Webhook event ID")
    event_type: str = Field(..., description="Event type")
    resource_type: str = Field(..., description="Resource type")
    resource: Dict[str, Any] = Field(..., description="Event resource data")
    create_time: str = Field(..., description="Event creation time") 