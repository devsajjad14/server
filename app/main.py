from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.checkout.paypal.routes import router as paypal_router
from app.checkout.routes import router as checkout_router
from app.checkout.paypal.test_routes import router as paypal_test_router
from app.checkout.credit_card.stripe.routes import router as stripe_router
from app.checkout.credit_card.stripe.test_routes import router as stripe_test_router
from app.checkout.credit_card.square.routes import router as square_router
from app.checkout.credit_card.square.test_routes import router as square_test_router
from app.checkout.credit_card.authorize.routes import router as authorize_router
from app.checkout.credit_card.authorize.test_routes import router as authorize_test_router
from app.checkout.credit_card.paypal_commerce.routes import router as paypal_card_router
from app.checkout.credit_card.paypal_commerce.test_routes import router as paypal_card_test_router
from app.checkout.klarna.routes import router as klarna_router
from app.checkout.klarna.test_routes import router as klarna_test_router
from app.admin.routes import router as admin_router
from config import settings
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="E-commerce API",
    description="FastAPI backend for e-commerce application with PayPal Commerce Platform integration",
    version="1.0.0"
)

# Add CORS middleware to allow requests from Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],  # Use env var
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(paypal_router, prefix="/checkout/paypal")
app.include_router(checkout_router, prefix="/checkout")
app.include_router(paypal_test_router, prefix="/checkout/paypal")
app.include_router(stripe_router, prefix="/checkout/credit-card/stripe")
app.include_router(stripe_test_router, prefix="/checkout/credit-card/stripe")
app.include_router(square_router, prefix="/checkout/credit-card/square")
app.include_router(square_test_router, prefix="/checkout/credit-card/square")
app.include_router(authorize_router, prefix="/checkout/credit-card/authorize")
app.include_router(authorize_test_router, prefix="/checkout/credit-card/authorize")
app.include_router(paypal_card_router, prefix="/checkout/credit-card/paypal-commerce")
app.include_router(paypal_card_test_router, prefix="/checkout/credit-card/paypal-commerce")
app.include_router(klarna_router, prefix="/checkout/klarna")
app.include_router(klarna_test_router, prefix="/checkout/klarna")
app.include_router(admin_router, prefix="/admin")

@app.get("/")
async def root():
    return {"message": "Welcome to Fastapi server 1.0.1"} 