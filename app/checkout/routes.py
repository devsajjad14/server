from fastapi import APIRouter
from app.checkout.credit_card.authorize.routes import router as authorize_router
from app.checkout.credit_card.paypal_commerce.routes import router as paypal_commerce_router
from app.checkout.credit_card.paypal_commerce.test_routes import router as paypal_commerce_test_router
from app.checkout.klarna.routes import router as klarna_router

router = APIRouter()

# Authorize.Net
router.include_router(authorize_router, prefix="/credit-card/authorize")
# PayPal Commerce Platform Card
router.include_router(paypal_commerce_router, prefix="/credit-card/paypal-commerce")
router.include_router(paypal_commerce_test_router, prefix="/credit-card/paypal-commerce")
# Klarna
router.include_router(klarna_router, prefix="/klarna") 