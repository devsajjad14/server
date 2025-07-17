import os
import json
import logging
from typing import Dict, Any, Optional, List
from decimal import Decimal
import httpx
from datetime import datetime, timedelta
import paypalrestsdk
from config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PayPalCommerceService:
    """PayPal Commerce Platform integration service"""
    
    def __init__(self, client_id: str = None, client_secret: str = None, mode: str = None):
        # Use provided credentials or fall back to environment variables
        self.client_id = client_id or settings.PAYPAL_CLIENT_ID
        self.client_secret = client_secret or settings.PAYPAL_CLIENT_SECRET
        self.mode = mode or settings.PAYPAL_MODE
        self.base_url = "https://api-m.sandbox.paypal.com" if self.mode == "sandbox" else "https://api-m.paypal.com"
        
        # Validate configuration
        if not self.client_id or not self.client_secret:
            logger.warning("PayPal configuration is incomplete. Credentials must be provided or set in environment variables.")
        
        # Initialize PayPal SDK with current credentials
        if self.client_id and self.client_secret:
            paypalrestsdk.configure({
                "mode": self.mode,
                "client_id": self.client_id,
                "client_secret": self.client_secret
            })
        
        self.access_token = None
        self.token_expires_at = None
    
    def update_credentials(self, client_id: str, client_secret: str, mode: str = None):
        """Update credentials dynamically"""
        self.client_id = client_id
        self.client_secret = client_secret
        self.mode = mode or self.mode
        self.base_url = "https://api-m.sandbox.paypal.com" if self.mode == "sandbox" else "https://api-m.paypal.com"
        
        # Reconfigure PayPal SDK with new credentials
        paypalrestsdk.configure({
            "mode": self.mode,
            "client_id": self.client_id,
            "client_secret": self.client_secret
        })
        
        # Reset access token cache
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
            self.token_expires_at = datetime.utcnow() + timedelta(minutes=55)
            
            return self.access_token
    
    async def test_connection(self, client_id: str, client_secret: str, mode: str = "sandbox") -> Dict[str, Any]:
        """Test PayPal connection with provided credentials"""
        try:
            logger.info(f"Testing PayPal connection for mode: {mode}")
            
            # Set base URL based on mode
            base_url = "https://api-m.sandbox.paypal.com" if mode == "sandbox" else "https://api-m.paypal.com"
            
            # Test by getting an access token
            async with httpx.AsyncClient() as client:
                auth_response = await client.post(
                    f"{base_url}/v1/oauth2/token",
                    auth=(client_id, client_secret),
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    data={"grant_type": "client_credentials"},
                    timeout=30.0
                )
                
                if auth_response.status_code == 200:
                    token_data = auth_response.json()
                    logger.info("PayPal connection test successful")
                    return {
                        "success": True,
                        "message": "PayPal connection test successful",
                        "details": {
                            "mode": mode,
                            "token_type": token_data.get("token_type"),
                            "expires_in": token_data.get("expires_in")
                        }
                    }
                else:
                    error_data = auth_response.json() if auth_response.text else {}
                    error_message = error_data.get("error_description", "Authentication failed")
                    logger.error(f"PayPal connection test failed: {error_message}")
                    return {
                        "success": False,
                        "error": error_message,
                        "details": {
                            "mode": mode,
                            "status_code": auth_response.status_code
                        }
                    }
                    
        except Exception as e:
            logger.error(f"Error testing PayPal connection: {str(e)}")
            return {
                "success": False,
                "error": f"Connection test failed: {str(e)}",
                "details": {
                    "mode": mode,
                    "exception": str(e)
                }
            } 