from fastapi import APIRouter, HTTPException, Request
from typing import Dict, Any
import logging
from datetime import datetime
import httpx
import uuid

router = APIRouter(
    tags=["PayPal Card Checkout"],
    prefix="",
    responses={404: {"description": "Not found"}},
)

PAYPAL_API_BASE = {
    "sandbox": "https://api-m.sandbox.paypal.com",
    "live": "https://api-m.paypal.com"
}

@router.post("/process-payment", summary="Process Paypal Commerce Payment")
async def process_paypal_commerce_payment(request: Request):
    """
    PayPal Commerce Platform card payment processing endpoint (real API integration)
    """
    try:
        body = await request.json()
        logging.info(f"Received PayPal Commerce payment payload: {body}")
        payment_config = body.get('payment_config', {})
        logging.info(f"Extracted payment_config: {payment_config}")
        checkout_data = {k: v for k, v in body.items() if k != 'payment_config'}
        payment_method_data = checkout_data.get('payment_method', {})
        logging.info(f"Extracted payment_method_data: {payment_method_data}")

        # Validate payment configuration
        client_id = payment_config.get('client_id')
        client_secret = payment_config.get('client_secret')
        environment = payment_config.get('environment', 'sandbox')
        missing_fields = []
        if not client_id:
            missing_fields.append('client_id')
        if not client_secret:
            missing_fields.append('client_secret')
        card_number = payment_method_data.get('card_number', '')
        expiry_month = str(payment_method_data.get('expiry_month', '')).zfill(2)
        expiry_year = str(payment_method_data.get('expiry_year', ''))
        cvc = payment_method_data.get('cvc', '')
        name_on_card = payment_method_data.get('name_on_card', '')
        if not card_number:
            missing_fields.append('card_number')
        if not expiry_month or not expiry_year:
            missing_fields.append('expiry_month/expiry_year')
        if not cvc:
            missing_fields.append('cvc')
        if not name_on_card:
            missing_fields.append('name_on_card')
        if missing_fields:
            logging.error(f"Missing required fields: {missing_fields}")
            raise HTTPException(status_code=400, detail=f"Missing required fields: {missing_fields}")

        # Extract payment method from the request
        # payment_method_data = checkout_data.get('payment_method', {})
        # card_number = payment_method_data.get('card_number', '')
        # expiry_month = str(payment_method_data.get('expiry_month', '')).zfill(2)
        # expiry_year = str(payment_method_data.get('expiry_year', ''))
        # cvc = payment_method_data.get('cvc', '')
        # name_on_card = payment_method_data.get('name_on_card', '')
        billing_address = checkout_data.get('billing_address', {})
        # Ensure amount is formatted to two decimal places for PayPal
        amount = "{:.2f}".format(float(checkout_data.get('total_amount', '0.00')))
        currency = checkout_data.get('currency', 'USD').upper()
        order_id = checkout_data.get('order_id', '')

        # Step 1: Get OAuth2 access token from PayPal
        api_base = PAYPAL_API_BASE.get(environment, PAYPAL_API_BASE['sandbox'])
        async with httpx.AsyncClient(timeout=30.0) as client:
            token_resp = await client.post(
                f"{api_base}/v1/oauth2/token",
                data={"grant_type": "client_credentials"},
                auth=(client_id, client_secret),
                headers={"Accept": "application/json", "Accept-Language": "en_US"}
            )
            if token_resp.status_code != 200:
                logging.error(f"PayPal OAuth error: {token_resp.text}")
                raise HTTPException(status_code=502, detail=f"PayPal OAuth error: {token_resp.text}")
            access_token = token_resp.json().get('access_token')
            if not access_token:
                raise HTTPException(status_code=502, detail="Failed to obtain PayPal access token")

        # Step 2: Create PayPal order with card payment_source
        paypal_request_id = str(uuid.uuid4())
        order_payload = {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "reference_id": order_id,
                    "amount": {
                        "currency_code": currency,
                        "value": amount
                    },
                    "description": f"Order {order_id}"
                }
            ],
            "payment_source": {
                "card": {
                    "number": card_number,
                    "expiry": f"{expiry_year}-{expiry_month}",
                    "security_code": cvc,
                    "name": name_on_card,
                    "billing_address": {
                        "address_line_1": billing_address.get('line1', ''),
                        "address_line_2": billing_address.get('line2', ''),
                        "admin_area_2": billing_address.get('city', ''),
                        "admin_area_1": billing_address.get('state', ''),
                        "postal_code": billing_address.get('postal_code', ''),
                        "country_code": billing_address.get('country_code', 'US')
                    }
                }
            }
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
            "PayPal-Request-Id": paypal_request_id
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            order_resp = await client.post(
                f"{api_base}/v2/checkout/orders",
                json=order_payload,
                headers=headers
            )
        if order_resp.status_code not in (201, 200):
            error_json = order_resp.json()
            # Check for PAYEE_NOT_ENABLED_FOR_CARD_PROCESSING
            details = error_json.get('details', [])
            for detail in details:
                if detail.get('issue') == 'PAYEE_NOT_ENABLED_FOR_CARD_PROCESSING':
                    user_message = (
                        'Your PayPal account is not enabled for card transactions. '
                        'Please contact PayPal to activate Advanced Credit and Debit Card Payments and try again.'
                    )
                    logging.error(f"PayPal order creation error: {error_json}")
                    raise HTTPException(status_code=400, detail={
                        'success': False,
                        'error': user_message,
                        'paypal_error': error_json,
                        'order_id': order_id
                    })
            logging.error(f"PayPal order creation error: {order_resp.text}")
            raise HTTPException(status_code=502, detail=f"PayPal order creation error: {order_resp.text}")
        order_result = order_resp.json()
        paypal_order_id = order_result.get('id')
        status = order_result.get('status')
        if status != 'COMPLETED':
            # Try to capture the order if not already completed
            async with httpx.AsyncClient(timeout=30.0) as client:
                capture_resp = await client.post(
                    f"{api_base}/v2/checkout/orders/{paypal_order_id}/capture",
                    headers=headers
                )
            if capture_resp.status_code not in (201, 200):
                logging.error(f"PayPal order capture error: {capture_resp.text}")
                raise HTTPException(status_code=502, detail=f"PayPal order capture error: {capture_resp.text}")
            capture_result = capture_resp.json()
            status = capture_result.get('status', status)
        else:
            capture_result = order_result

        success = status in ('COMPLETED', 'APPROVED')
        response_data = {
            "success": success,
            "order_id": order_id,
            "paypal_order_id": paypal_order_id,
            "status": status,
            "message": "PayPal Commerce card payment processed successfully" if success else f"PayPal payment status: {status}",
            "amount": amount,
            "currency": currency,
            "timestamp": datetime.utcnow().isoformat(),
            "raw": order_result if success else capture_result
        }
        if not success:
            raise HTTPException(status_code=400, detail=response_data)
        return response_data

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Unexpected error in process_paypal_commerce_payment: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}") 