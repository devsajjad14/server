from fastapi import APIRouter, HTTPException, Request
import httpx

router = APIRouter(
    tags=["PayPal Card Checkout"],
    prefix="",
    responses={404: {"description": "Not found"}},
)

@router.post("/test-connection", summary="Test Paypal Commerce Connection")
async def test_paypal_commerce_connection(request: Request):
    """
    Test PayPal Commerce Platform API credentials by attempting to obtain an access token.
    """
    try:
        body = await request.json()
        client_id = body.get('client_id')
        client_secret = body.get('client_secret')
        environment = body.get('environment', 'sandbox')
        if not client_id or not client_secret:
            raise HTTPException(status_code=400, detail="PayPal Commerce credentials are required.")

        api_url = "https://api-m.sandbox.paypal.com/v1/oauth2/token" if environment == "sandbox" else "https://api-m.paypal.com/v1/oauth2/token"
        auth = (client_id, client_secret)
        headers = {"Accept": "application/json", "Accept-Language": "en_US"}
        data = {"grant_type": "client_credentials"}

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(api_url, headers=headers, data=data, auth=auth)

        if response.status_code == 200:
            return {"success": True, "message": "PayPal Commerce connection successful."}
        else:
            return {"success": False, "message": f"PayPal Commerce connection failed: {response.text}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PayPal Commerce test connection error: {str(e)}") 