from fastapi import APIRouter, HTTPException, Request
from typing import Dict, Any
import logging
from datetime import datetime
import httpx
from .test_routes import router as test_router

router = APIRouter(
    tags=["Authorize.Net Checkout"],
    prefix="",
    responses={404: {"description": "Not found"}},
)
router.include_router(test_router, prefix="")

@router.post("/process-payment")
async def process_authorize_payment(request: Request):
    """
    Authorize.Net payment processing endpoint using REST API (httpx)
    """
    try:
        body = await request.json()
        payment_config = body.get('payment_config', {})
        checkout_data = {k: v for k, v in body.items() if k != 'payment_config'}

        # Validate payment configuration
        api_login_id = payment_config.get('api_login_id')
        transaction_key = payment_config.get('transaction_key')
        environment = payment_config.get('environment', 'sandbox')
        if not api_login_id or not transaction_key:
            raise HTTPException(status_code=400, detail="Authorize.Net credentials are required in payment configuration")

        # Extract payment method from the request
        payment_method_data = checkout_data.get('payment_method', {})
        card_number = payment_method_data.get('card_number', '')
        expiry_month = str(payment_method_data.get('expiry_month', '')).zfill(2)
        expiry_year = str(payment_method_data.get('expiry_year', ''))
        cvc = payment_method_data.get('cvc', '')
        name_on_card = payment_method_data.get('name_on_card', '')

        # Format expiration date as MMYY
        exp_date = f"{expiry_month}{expiry_year[-2:]}"

        # Build the Authorize.Net REST API payload
        payload = {
            "createTransactionRequest": {
                "merchantAuthentication": {
                    "name": api_login_id,
                    "transactionKey": transaction_key
                },
                "transactionRequest": {
                    "transactionType": "authCaptureTransaction",
                    "amount": str(checkout_data.get('total_amount', '0.00')),
                    "payment": {
                        "creditCard": {
                            "cardNumber": card_number,
                            "expirationDate": exp_date,  # MMYY
                            "cardCode": cvc
                        }
                    },
                    "order": {
                        "invoiceNumber": str(checkout_data.get('order_id', '')),
                        "description": f"Order {checkout_data.get('order_id', '')}"
                    },
                    "billTo": {
                        "firstName": checkout_data.get('customer', {}).get('first_name', name_on_card.split(' ')[0] if name_on_card else ''),
                        "lastName": checkout_data.get('customer', {}).get('last_name', name_on_card.split(' ')[1] if name_on_card and len(name_on_card.split(' ')) > 1 else ''),
                        "address": checkout_data.get('billing_address', {}).get('line1', ''),
                        "city": checkout_data.get('billing_address', {}).get('city', ''),
                        "state": checkout_data.get('billing_address', {}).get('state', ''),
                        "zip": checkout_data.get('billing_address', {}).get('postal_code', ''),
                        "country": checkout_data.get('billing_address', {}).get('country_code', 'US'),
                        "email": checkout_data.get('customer', {}).get('email', '')
                    }
                }
            }
        }

        # Choose endpoint based on environment
        api_url = "https://apitest.authorize.net/xml/v1/request.api" if environment == "sandbox" else "https://api2.authorize.net/xml/v1/request.api"

        # Send the request to Authorize.Net
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(api_url, json=payload, headers={"Content-Type": "application/json"})

        if response.status_code != 200:
            logging.error(f"Authorize.Net API error: {response.text}")
            raise HTTPException(status_code=502, detail=f"Authorize.Net API error: {response.text}")

        result = response.json()
        logging.info(f"Authorize.Net API response: {result}")

        # Parse the response for transaction status
        transaction_response = result.get('transactionResponse', {})
        messages = result.get('messages', {}).get('message', [{}])
        message_text = messages[0].get('text', '') if messages else ''
        success = transaction_response.get('responseCode') == '1'
        transaction_id = transaction_response.get('transId', '')
        auth_code = transaction_response.get('authCode', '')
        status = 'approved' if success else 'declined'
        error_message = transaction_response.get('errors', [{}])[0].get('errorText', '') if transaction_response.get('errors') else message_text

        response_data = {
            "success": success,
            "order_id": checkout_data.get('order_id'),
            "transaction_id": transaction_id,
            "auth_code": auth_code,
            "status": status,
            "message": message_text if success else error_message,
            "amount": checkout_data.get('total_amount'),
            "currency": checkout_data.get('currency', 'usd'),
            "timestamp": datetime.utcnow().isoformat(),
            "raw": result
        }
        if not success:
            raise HTTPException(status_code=400, detail=response_data)
        return response_data

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Unexpected error in process_authorize_payment: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}") 