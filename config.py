import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Settings:
    """Application settings"""
    
    # PayPal Commerce Platform Configuration
    PAYPAL_CLIENT_ID: str = os.getenv("PAYPAL_CLIENT_ID", "")
    PAYPAL_CLIENT_SECRET: str = os.getenv("PAYPAL_CLIENT_SECRET", "")
    PAYPAL_MODE: str = os.getenv("PAYPAL_MODE", "sandbox")  # sandbox or live
    
    # Application Configuration
    APP_ENV: str = os.getenv("APP_ENV", "development")
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"
    
    # Frontend URLs
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")
    BACKEND_URL: str = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
    
    # Database Configuration (if needed)
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    
    @classmethod
    def validate_paypal_config(cls) -> bool:
        """Validate PayPal configuration"""
        if not cls.PAYPAL_CLIENT_ID or not cls.PAYPAL_CLIENT_SECRET:
            return False
        return True
    
    @classmethod
    def get_paypal_config(cls) -> dict:
        """Get PayPal configuration"""
        return {
            "client_id": cls.PAYPAL_CLIENT_ID,
            "client_secret": cls.PAYPAL_CLIENT_SECRET,
            "mode": cls.PAYPAL_MODE
        }

# Create settings instance
settings = Settings() 