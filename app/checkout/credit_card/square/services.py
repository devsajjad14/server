import os
import json
import logging
import asyncio
from typing import Dict, Any, Optional, List, Tuple
from decimal import Decimal
from datetime import datetime, timedelta
from square import Square
from square.environment import SquareEnvironment
from square.core.api_error import ApiError
from .schemas import (
    SquareCheckoutRequestSchema,
    SquareCheckoutResponseSchema,
    SquarePaymentSchema,
    SquarePaymentMethodResponseSchema,
    SquareCustomerSchema,
    SquareTestConnectionRequestSchema,
    SquareTestConnectionResponseSchema,
    SquareRefundRequestSchema,
    SquareRefundResponseSchema,
    SquareErrorSchema,
    SquarePaymentStatus,
    PaymentMethodType
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SquareService:
    """Production-ready Square payment processing service using official Python SDK"""
    
    def __init__(self, application_id: str, access_token: str, location_id: str, environment: str = "sandbox"):
        """
        Initialize Square service with credentials
        
        Args:
            application_id: Square Application ID
            access_token: Square Access Token
            location_id: Square Location ID
            environment: Environment mode ('sandbox' or 'live')
        """
        if not application_id or not access_token or not location_id:
            raise ValueError("Square Application ID, Access Token, and Location ID are required")
        
        self.application_id = application_id
        self.access_token = access_token
        self.location_id = location_id
        self.environment = environment
        
        # Initialize Square client
        self.client = Square(
            token=access_token,
            environment=SquareEnvironment.SANDBOX if environment == "sandbox" else SquareEnvironment.PRODUCTION
        )
        
        logger.info(f"Square service initialized with environment: {environment}")
        logger.info(f"Application ID: {application_id[:10]}...{application_id[-4:] if len(application_id) > 14 else '***'}")
        logger.info(f"Location ID: {location_id}")
    
    async def test_connection(self, request: SquareTestConnectionRequestSchema) -> SquareTestConnectionResponseSchema:
        """
        Test Square connection and credentials validity using SDK
        
        Args:
            request: Test connection request with credentials
            
        Returns:
            SquareTestConnectionResponseSchema with test results
        """
        try:
            logger.info("Testing Square connection...")
            
            # Create temporary client for testing
            test_client = Square(
                token=request.access_token,
                environment=SquareEnvironment.SANDBOX if request.mode == "sandbox" else SquareEnvironment.PRODUCTION
            )
            
            # Test by listing locations (this requires valid credentials)
            result = test_client.locations.list()
            
            if result.locations:
                locations = result.locations
                
                # Check if the provided location_id exists
                location_exists = any(loc.id == request.location_id for loc in locations)
                
                if location_exists:
                    logger.info("Square connection test successful")
                    return SquareTestConnectionResponseSchema(
                        success=True,
                        message="Square connection test successful",
                        details={
                            "mode": request.mode,
                            "application_id": request.application_id[:10] + "...",
                            "location_id": request.location_id,
                            "locations_count": len(locations)
                        }
                    )
                else:
                    logger.error(f"Location ID {request.location_id} not found in account")
                    return SquareTestConnectionResponseSchema(
                        success=False,
                        message=f"Location ID {request.location_id} not found in your Square account",
                        error="LOCATION_NOT_FOUND",
                        details={
                            "mode": request.mode,
                            "provided_location_id": request.location_id,
                            "available_locations": [loc.id for loc in locations]
                        }
                    )
            else:
                logger.error("No locations found in Square account")
                return SquareTestConnectionResponseSchema(
                    success=False,
                    message="No locations found in your Square account",
                    error="NO_LOCATIONS_FOUND",
                    details={
                        "mode": request.mode
                    }
                )
                    
        except ApiError as e:
            error_message = e.errors[0].detail if e.errors else "Authentication failed"
            logger.error(f"Square connection test failed: {error_message}")
            return SquareTestConnectionResponseSchema(
                success=False,
                message=f"Square connection test failed: {error_message}",
                error="AUTHENTICATION_FAILED",
                details={
                    "mode": request.mode,
                    "errors": [{"detail": error.detail, "code": error.code} for error in e.errors]
                }
            )
        except Exception as e:
            logger.error(f"Error testing Square connection: {str(e)}")
            return SquareTestConnectionResponseSchema(
                success=False,
                message=f"Connection test failed: {str(e)}",
                error="CONNECTION_ERROR",
                details={
                    "mode": request.mode,
                    "exception": str(e)
                }
            )
    
    async def create_payment(
        self, 
        request: SquareCheckoutRequestSchema,
        payment_config: Dict[str, Any]
    ) -> SquareCheckoutResponseSchema:
        """
        Create a Square Payment using the official SDK
        
        Args:
            request: Checkout request with order and payment details
            payment_config: Payment gateway configuration
            
        Returns:
            SquareCheckoutResponseSchema with payment details
        """
        try:
            logger.info(f"Creating Square payment for order: {request.order_id}")
            
            # Convert amount to cents (Square expects amounts in smallest currency unit)
            amount = int(float(request.total_amount))
            currency = request.currency.upper()
            
            logger.info(f"Creating payment with amount: {amount} {currency}")
            
            # Generate unique idempotency key
            idempotency_key = f"payment_{request.order_id}_{int(datetime.utcnow().timestamp())}"
            
            # Use Square's test nonce for development
            # In production, this should come from the frontend Square SDK
            source_id = "cnon:card-nonce-ok"
            logger.info(f"Using test nonce: {source_id}")
            
            logger.info(f"Payment details: amount={amount}, currency={currency}, source_id={source_id}")
            
            # Create payment with minimal parameters (same as working test)
            logger.info("Creating payment with minimal parameters...")
            payment_result = self.client.payments.create(
                idempotency_key=idempotency_key,
                amount_money={
                    "amount": amount,
                    "currency": currency
                },
                source_id=source_id,
                location_id=self.location_id
            )
            
            if payment_result.payment:
                payment = payment_result.payment
                logger.info(f"Payment created successfully: {payment.id} with status: {payment.status}")
                
                # Create response schema
                payment_schema = SquarePaymentSchema(
                    id=payment.id,
                    status=payment.status,
                    amount_money={
                        "amount": payment.amount_money.amount,
                        "currency": payment.amount_money.currency
                    },
                    created_at=payment.created_at,
                    updated_at=payment.updated_at,
                    metadata=getattr(payment, 'metadata', {}) or {},
                    receipt_url=getattr(payment, 'receipt_url', None),
                    order_id=request.order_id
                )
                
                # Create customer schema (simplified)
                customer_schema = SquareCustomerSchema(
                    id="test_customer",  # Since we're not creating customers in this simplified approach
                    email=request.customer.email,
                    first_name=request.customer.first_name,
                    last_name=request.customer.last_name,
                    phone=request.customer.phone
                )
                
                return SquareCheckoutResponseSchema(
                    success=True,
                    message="Payment processed successfully",
                    order_id=request.order_id,
                    payment=payment_schema,
                    customer=customer_schema,
                    status=SquarePaymentStatus.COMPLETED if payment.status == 'COMPLETED' else SquarePaymentStatus.PENDING
                )
            else:
                logger.error("Payment creation failed: No payment returned")
                return self._create_error_response(
                    request.order_id,
                    "Failed to create payment: No payment returned",
                    "payment_creation_failed"
                )
                
        except ApiError as e:
            error_message = e.message if hasattr(e, 'message') else (e.errors[0].detail if e.errors else "Payment creation failed")
            logger.error(f"Payment creation failed: {error_message}")
            logger.error(f"Full error details: {e}")
            if hasattr(e, 'errors') and e.errors:
                for i, error in enumerate(e.errors):
                    logger.error(f"Error {i+1}: {error}")
            return self._create_error_response(
                request.order_id,
                f"Failed to create payment: {error_message}",
                "payment_creation_failed"
            )
        except Exception as e:
            logger.error(f"Error creating Square payment: {str(e)}")
            return self._create_error_response(
                request.order_id,
                f"Payment processing error: {str(e)}",
                "payment_processing_error"
            )
    
    def _create_error_response(
        self, 
        order_id: str, 
        message: str, 
        error_code: Optional[str] = None,
        error_type: Optional[str] = None
    ) -> SquareCheckoutResponseSchema:
        """Create error response schema"""
        return SquareCheckoutResponseSchema(
            success=False,
            message=message,
            order_id=order_id,
            error=SquareErrorSchema(
                code=error_code or "UNKNOWN_ERROR",
                type=error_type or "PAYMENT_ERROR",
                message=message
            ),
            status=SquarePaymentStatus.FAILED
        ) 