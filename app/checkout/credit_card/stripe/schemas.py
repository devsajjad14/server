from pydantic import BaseModel, Field, validator, model_validator
from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import datetime
from enum import Enum


class PaymentMethodType(str, Enum):
    """Supported payment method types"""
    CARD = "card"
    WALLET = "wallet"  # Apple Pay, Google Pay


class StripePaymentIntentStatus(str, Enum):
    """Stripe PaymentIntent statuses"""
    REQUIRES_PAYMENT_METHOD = "requires_payment_method"
    REQUIRES_CONFIRMATION = "requires_confirmation"
    REQUIRES_ACTION = "requires_action"
    PROCESSING = "processing"
    REQUIRES_CAPTURE = "requires_capture"
    CANCELED = "canceled"
    SUCCEEDED = "succeeded"


class StripeCardBrand(str, Enum):
    """Supported card brands"""
    VISA = "visa"
    MASTERCARD = "mastercard"
    AMEX = "amex"
    DISCOVER = "discover"
    DINERS_CLUB = "diners_club"
    JCB = "jcb"
    UNIONPAY = "unionpay"


class CustomerSchema(BaseModel):
    """Customer information schema"""
    email: str = Field(..., description="Customer email address")
    first_name: str = Field(..., min_length=1, max_length=100, description="Customer first name")
    last_name: str = Field(..., min_length=1, max_length=100, description="Customer last name")
    phone: Optional[str] = Field(None, max_length=20, description="Customer phone number")
    metadata: Optional[Dict[str, str]] = Field(default_factory=dict, description="Additional customer metadata")


class AddressSchema(BaseModel):
    """Address information schema"""
    line1: str = Field(..., min_length=1, max_length=200, description="Address line 1")
    line2: Optional[str] = Field(None, max_length=200, description="Address line 2")
    city: str = Field(..., min_length=1, max_length=100, description="City")
    state: str = Field(..., min_length=1, max_length=100, description="State/Province")
    postal_code: str = Field(..., min_length=1, max_length=20, description="Postal code")
    country_code: str = Field(..., min_length=2, max_length=2, description="ISO 2-letter country code")

    @validator('country_code')
    def validate_country_code(cls, v):
        if not v.isalpha() or len(v) != 2:
            raise ValueError('Country code must be a 2-letter ISO code')
        return v.upper()


class OrderItemSchema(BaseModel):
    """Order item schema"""
    product_id: str = Field(..., description="Product identifier")
    name: str = Field(..., min_length=1, max_length=255, description="Product name")
    quantity: int = Field(..., gt=0, le=999, description="Item quantity")
    unit_price: Decimal = Field(..., gt=0, description="Unit price in smallest currency unit")
    currency: str = Field(default="usd", min_length=3, max_length=3, description="Currency code")
    metadata: Optional[Dict[str, str]] = Field(default_factory=dict, description="Additional item metadata")

    @validator('currency')
    def validate_currency(cls, v):
        return v.lower()


class StripePaymentMethodSchema(BaseModel):
    """Stripe payment method details"""
    type: PaymentMethodType = Field(..., description="Payment method type")
    card_number: Optional[str] = Field(None, min_length=13, max_length=19, description="Card number")
    expiry_month: Optional[int] = Field(None, ge=1, le=12, description="Expiry month")
    expiry_year: Optional[int] = Field(None, ge=2024, le=2100, description="Expiry year")
    cvc: Optional[str] = Field(None, min_length=3, max_length=4, description="Card verification code")
    name_on_card: Optional[str] = Field(None, max_length=100, description="Name on card")
    save_payment_method: bool = Field(default=False, description="Whether to save payment method for future use")

    @validator('card_number')
    def validate_card_number(cls, v):
        if v is not None:
            # Remove spaces and dashes
            v = ''.join(filter(str.isdigit, v))
            if not v.isdigit() or len(v) < 13 or len(v) > 19:
                raise ValueError('Invalid card number format')
        return v

    @validator('cvc')
    def validate_cvc(cls, v):
        if v is not None:
            if not v.isdigit() or len(v) < 3 or len(v) > 4:
                raise ValueError('Invalid CVC format')
        return v

    @model_validator(mode='after')
    def validate_card_fields(self):
        if self.type == PaymentMethodType.CARD:
            required_fields = ['card_number', 'expiry_month', 'expiry_year', 'cvc']
            missing_fields = [field for field in required_fields if not getattr(self, field)]
            if missing_fields:
                raise ValueError(f'Card payment method requires: {", ".join(missing_fields)}')
        return self


class StripeCheckoutRequestSchema(BaseModel):
    """Complete Stripe checkout request schema"""
    order_id: str = Field(..., min_length=1, max_length=255, description="Unique order identifier")
    customer: CustomerSchema = Field(..., description="Customer information")
    items: List[OrderItemSchema] = Field(..., min_items=1, max_items=100, description="Order items")
    shipping_address: AddressSchema = Field(..., description="Shipping address")
    billing_address: Optional[AddressSchema] = Field(None, description="Billing address (uses shipping if not provided)")
    subtotal: Decimal = Field(..., gt=0, description="Order subtotal in smallest currency unit")
    tax_amount: Decimal = Field(default=0, ge=0, description="Tax amount in smallest currency unit")
    shipping_amount: Decimal = Field(default=0, ge=0, description="Shipping cost in smallest currency unit")
    discount_amount: Decimal = Field(default=0, ge=0, description="Discount amount in smallest currency unit")
    total_amount: Decimal = Field(..., gt=0, description="Total order amount in smallest currency unit")
    currency: str = Field(default="usd", min_length=3, max_length=3, description="Currency code")
    payment_method: StripePaymentMethodSchema = Field(..., description="Payment method details")
    metadata: Optional[Dict[str, str]] = Field(default_factory=dict, description="Additional order metadata")
    notes: Optional[str] = Field(None, max_length=1000, description="Order notes")
    return_url: Optional[str] = Field(None, description="Return URL after payment completion")
    cancel_url: Optional[str] = Field(None, description="Cancel URL if payment is cancelled")

    @validator('currency')
    def validate_currency(cls, v):
        return v.lower()

    @model_validator(mode='after')
    def validate_amounts(self):
        subtotal = self.subtotal
        tax_amount = self.tax_amount
        shipping_amount = self.shipping_amount
        discount_amount = self.discount_amount
        total_amount = self.total_amount
        
        calculated_total = subtotal + tax_amount + shipping_amount - discount_amount
        
        if abs(calculated_total - total_amount) > Decimal('0.01'):
            raise ValueError('Total amount does not match sum of subtotal, tax, shipping, and discount')
        
        return self


class StripePaymentIntentSchema(BaseModel):
    """Stripe PaymentIntent response schema"""
    id: str = Field(..., description="PaymentIntent ID")
    client_secret: str = Field(..., description="Client secret for frontend confirmation")
    status: StripePaymentIntentStatus = Field(..., description="PaymentIntent status")
    amount: int = Field(..., description="Amount in smallest currency unit")
    currency: str = Field(..., description="Currency code")
    created: datetime = Field(..., description="Creation timestamp")
    metadata: Dict[str, str] = Field(default_factory=dict, description="PaymentIntent metadata")
    next_action: Optional[Dict[str, Any]] = Field(None, description="Next action required")
    payment_method_types: List[str] = Field(default_factory=list, description="Supported payment method types")


class StripePaymentMethodResponseSchema(BaseModel):
    """Stripe PaymentMethod response schema"""
    id: str = Field(..., description="PaymentMethod ID")
    type: str = Field(..., description="Payment method type")
    card: Optional[Dict[str, Any]] = Field(None, description="Card details")
    billing_details: Optional[Dict[str, Any]] = Field(None, description="Billing details")
    created: datetime = Field(..., description="Creation timestamp")
    customer: Optional[str] = Field(None, description="Customer ID if attached")


class StripeCustomerSchema(BaseModel):
    """Stripe Customer response schema"""
    id: str = Field(..., description="Customer ID")
    email: str = Field(..., description="Customer email")
    name: Optional[str] = Field(None, description="Customer full name")
    phone: Optional[str] = Field(None, description="Customer phone")
    created: datetime = Field(..., description="Creation timestamp")
    metadata: Dict[str, str] = Field(default_factory=dict, description="Customer metadata")


class StripeCheckoutResponseSchema(BaseModel):
    """Stripe checkout response schema"""
    success: bool = Field(..., description="Operation success status")
    payment_intent: Optional[StripePaymentIntentSchema] = Field(None, description="PaymentIntent details")
    payment_method: Optional[StripePaymentMethodResponseSchema] = Field(None, description="PaymentMethod details")
    customer: Optional[StripeCustomerSchema] = Field(None, description="Customer details")
    order_id: str = Field(..., description="Order identifier")
    amount: int = Field(..., description="Total amount in smallest currency unit")
    currency: str = Field(..., description="Currency code")
    status: str = Field(..., description="Payment status")
    message: str = Field(..., description="Response message")
    requires_action: bool = Field(default=False, description="Whether additional action is required")
    next_action: Optional[Dict[str, Any]] = Field(None, description="Next action details")
    error: Optional[str] = Field(None, description="Error message if operation failed")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")


class StripePaymentConfirmRequestSchema(BaseModel):
    """Stripe payment confirmation request schema"""
    payment_intent_id: str = Field(..., description="PaymentIntent ID to confirm")
    payment_method_id: Optional[str] = Field(None, description="PaymentMethod ID")
    return_url: Optional[str] = Field(None, description="Return URL after confirmation")


class StripePaymentConfirmResponseSchema(BaseModel):
    """Stripe payment confirmation response schema"""
    success: bool = Field(..., description="Operation success status")
    payment_intent: Optional[StripePaymentIntentSchema] = Field(None, description="Updated PaymentIntent details")
    status: str = Field(..., description="Payment status")
    message: str = Field(..., description="Response message")
    error: Optional[str] = Field(None, description="Error message if operation failed")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")


class StripeRefundRequestSchema(BaseModel):
    """Stripe refund request schema"""
    payment_intent_id: str = Field(..., description="PaymentIntent ID to refund")
    amount: Optional[int] = Field(None, gt=0, description="Refund amount (partial refund if specified)")
    reason: Optional[str] = Field(None, description="Refund reason")
    metadata: Optional[Dict[str, str]] = Field(default_factory=dict, description="Refund metadata")


class StripeRefundResponseSchema(BaseModel):
    """Stripe refund response schema"""
    success: bool = Field(..., description="Operation success status")
    refund_id: Optional[str] = Field(None, description="Refund ID")
    amount: Optional[int] = Field(None, description="Refunded amount")
    status: str = Field(..., description="Refund status")
    message: str = Field(..., description="Response message")
    error: Optional[str] = Field(None, description="Error message if operation failed")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")


class StripeWebhookEventSchema(BaseModel):
    """Stripe webhook event schema"""
    id: str = Field(..., description="Event ID")
    type: str = Field(..., description="Event type")
    data: Dict[str, Any] = Field(..., description="Event data")
    created: datetime = Field(..., description="Event creation timestamp")
    livemode: bool = Field(..., description="Whether event is from live mode")
    api_version: Optional[str] = Field(None, description="API version")
    request: Optional[Dict[str, Any]] = Field(None, description="Request details")


class StripeErrorSchema(BaseModel):
    """Stripe error response schema"""
    error: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Stripe error code")
    error_type: Optional[str] = Field(None, description="Error type")
    decline_code: Optional[str] = Field(None, description="Card decline code")
    param: Optional[str] = Field(None, description="Parameter that caused the error")
    message: str = Field(..., description="Human-readable error message")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp") 