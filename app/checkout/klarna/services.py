import logging
import httpx
import base64
from pydantic import BaseModel
from typing import Optional, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class KlarnaTestConnectionRequestSchema(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    environment: str = "playground"  # or "live"
    region: Optional[str] = "North America"  # 'North America', 'Europe', 'Oceania'
    authorization: Optional[str] = None  # base64 string for Authorization header

class KlarnaTestConnectionResponseSchema(BaseModel):
    success: bool
    message: str
    error: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

class KlarnaSessionRequestSchema(BaseModel):
    order_id: str
    customer: Dict[str, Any]
    items: list
    shipping_address: Dict[str, Any]
    billing_address: Optional[Dict[str, Any]] = None
    subtotal: float
    tax_amount: float
    shipping_amount: float
    discount_amount: float
    total_amount: float
    currency: str = "USD"
    payment_config: Optional[Dict[str, Any]] = None
    merchant_urls: Optional[Dict[str, str]] = None

class KlarnaSessionResponseSchema(BaseModel):
    success: bool
    session_id: Optional[str] = None
    client_token: Optional[str] = None
    html_snippet: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    redirect_url: Optional[str] = None  # For frontend to use if desired

class KlarnaService:
    def __init__(self, username: Optional[str] = None, password: Optional[str] = None, environment: str = "playground", region: Optional[str] = "North America", authorization: Optional[str] = None):
        self.username = username
        self.password = password
        self.environment = environment
        self.region = region or "North America"
        self.authorization = authorization
        # Determine API base URL based on region and environment
        if self.region == "Europe":
            self.api_base = "https://api.klarna.com" if environment == "live" else "https://api.playground.klarna.com"
        elif self.region == "Oceania":
            self.api_base = "https://api-oc.klarna.com" if environment == "live" else "https://api-oc.playground.klarna.com"
        else:
            self.api_base = "https://api-na.klarna.com" if environment == "live" else "https://api-na.playground.klarna.com"

    async def test_connection(self, request: KlarnaTestConnectionRequestSchema) -> KlarnaTestConnectionResponseSchema:
        payload = {
            "purchase_country": "US",
            "purchase_currency": "USD",
            "locale": "en-US",
            "order_amount": 10000,
            "order_tax_amount": 1000,
            "order_lines": [
                {
                    "type": "physical",
                    "reference": "SKU123",
                    "name": "Blue T-Shirt",
                    "quantity": 1,
                    "unit_price": 10000,
                    "tax_rate": 1000,
                    "total_amount": 10000,
                    "total_tax_amount": 1000
                }
            ],
            "billing_address": {
                "given_name": "John",
                "family_name": "Doe",
                "email": "john@doe.com",
                "street_address": "Lombard St 10",
                "postal_code": "90210",
                "city": "Beverly Hills",
                "region": "CA",
                "phone": "333444555",
                "country": "US"
            },
            "customer": {
                "type": "person",
                "date_of_birth": "1995-10-20"
            },
            "merchant_urls": {
                "confirmation": "https://www.example.com/confirmation",
                "notification": "https://www.example.com/notification"
            }
        }
        headers = {
            "Content-Type": "application/json",
        }
        if request.authorization:
            headers["Authorization"] = f"Basic {request.authorization}"
            logger.info(f"Klarna outgoing Authorization: Basic {request.authorization[:6]}...{request.authorization[-6:]}")
        elif request.username and request.password:
            username = request.username.strip()
            password = request.password.strip()
            auth_str = f"{username}:{password}"
            encoded = base64.b64encode(auth_str.encode()).decode()
            headers["Authorization"] = f"Basic {encoded}"
            logger.info(f"Klarna outgoing Authorization: Basic {encoded[:6]}...{encoded[-6:]}")
        else:
            return KlarnaTestConnectionResponseSchema(
                success=False,
                message="Missing credentials: provide either authorization or username/password",
                error="MISSING_CREDENTIALS",
                details={}
            )
        # Set User-Agent to match cURL
        headers["User-Agent"] = "curl/7.79.1"
        # Use region from request if provided
        if hasattr(request, 'region') and request.region:
            if request.region == "Europe":
                self.api_base = "https://api.klarna.com" if request.environment == "live" else "https://api.playground.klarna.com"
            elif request.region == "Oceania":
                self.api_base = "https://api-oc.klarna.com" if request.environment == "live" else "https://api-oc.playground.klarna.com"
            else:
                self.api_base = "https://api-na.klarna.com" if request.environment == "live" else "https://api-na.playground.klarna.com"
        try:
            logger.info(f"Klarna outgoing endpoint: {self.api_base}/payments/v1/sessions")
            logger.info(f"Klarna outgoing headers: {{'Content-Type': 'application/json', 'Authorization': 'Basic ...', 'User-Agent': 'curl/7.79.1'}}")
            logger.info(f"Klarna outgoing payload: {payload}")
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{self.api_base}/payments/v1/sessions",
                    headers=headers,
                    json=payload
                )
            logger.info(f"Klarna response status: {response.status_code}")
            logger.info(f"Klarna response body: {response.text}")
            if response.status_code in (200, 201):
                logger.info("Klarna connection test successful")
                return KlarnaTestConnectionResponseSchema(
                    success=True,
                    message="Klarna connection test successful",
                    details={
                        "environment": self.environment,
                        "status_code": response.status_code,
                        "response": response.text
                    }
                )
            elif response.status_code == 401:
                logger.error("Klarna credentials are invalid (401 Unauthorized)")
                return KlarnaTestConnectionResponseSchema(
                    success=False,
                    message="Klarna credentials are invalid (401 Unauthorized)",
                    error="AUTHENTICATION_FAILED",
                    details={
                        "environment": self.environment,
                        "status_code": response.status_code,
                        "response": response.text
                    }
                )
            else:
                logger.error(f"Klarna connection test failed: {response.text}")
                return KlarnaTestConnectionResponseSchema(
                    success=False,
                    message=f"Klarna connection failed: {response.text}",
                    error="CONNECTION_ERROR",
                    details={
                        "environment": self.environment,
                        "status_code": response.status_code,
                        "response": response.text
                    }
                )
        except Exception as e:
            logger.error(f"Error testing Klarna connection: {str(e)}")
            return KlarnaTestConnectionResponseSchema(
                success=False,
                message=f"Klarna test connection error: {str(e)}",
                error="EXCEPTION",
                details={
                    "environment": self.environment,
                    "exception": str(e)
                }
            )

    async def create_session(self, request: KlarnaSessionRequestSchema) -> KlarnaSessionResponseSchema:
        """Create a Klarna payment session for a real order"""
        # Build Klarna payload from order
        payload = {
            "purchase_country": request.shipping_address.get("country_code", "US"),
            "purchase_currency": request.currency,
            "locale": "en-US",  # TODO: Make dynamic if needed
            "order_amount": int(request.total_amount * 100),
            "order_tax_amount": int(request.tax_amount * 100),
            "order_lines": [
                {
                    "type": "physical",
                    "reference": item.get("product_id"),
                    "name": item.get("name"),
                    "quantity": item.get("quantity"),
                    "unit_price": int(float(item.get("unit_price")) * 100),
                    "tax_rate": 0,  # TODO: Add real tax rate if available
                    "total_amount": int(float(item.get("unit_price")) * item.get("quantity") * 100),
                    "total_tax_amount": 0  # TODO: Add real tax if available
                } for item in request.items
            ],
            "billing_address": request.billing_address or request.shipping_address,
            "customer": request.customer,
            "merchant_urls": request.merchant_urls or {
                "confirmation": "https://www.example.com/confirmation",
                "notification": "https://www.example.com/notification"
            }
        }
        headers = {"Content-Type": "application/json"}
        # Use credentials from payment_config or env
        username = self.username
        password = self.password
        if request.payment_config:
            username = request.payment_config.get("username", username)
            password = request.payment_config.get("password", password)
        if username and password:
            auth_str = f"{username}:{password}"
            encoded = base64.b64encode(auth_str.encode()).decode()
            headers["Authorization"] = f"Basic {encoded}"
        elif self.authorization:
            headers["Authorization"] = f"Basic {self.authorization}"
        else:
            return KlarnaSessionResponseSchema(success=False, message="Missing Klarna credentials", error="MISSING_CREDENTIALS")
        headers["User-Agent"] = "curl/7.79.1"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{self.api_base}/payments/v1/sessions",
                    headers=headers,
                    json=payload
                )
            if response.status_code in (200, 201):
                data = response.json()
                return KlarnaSessionResponseSchema(
                    success=True,
                    session_id=data.get("session_id"),
                    client_token=data.get("client_token"),
                    html_snippet=data.get("html_snippet"),
                    message="Klarna session created",
                    details=data,
                    redirect_url=None  # Frontend will handle redirect after DB insertion
                )
            else:
                return KlarnaSessionResponseSchema(
                    success=False,
                    message=f"Klarna session creation failed: {response.text}",
                    error="SESSION_CREATION_FAILED",
                    details={"status_code": response.status_code, "response": response.text},
                    redirect_url=None
                )
        except Exception as e:
            return KlarnaSessionResponseSchema(
                success=False,
                message=f"Klarna session creation error: {str(e)}",
                error="EXCEPTION",
                details={"exception": str(e)},
                redirect_url=None
            ) 