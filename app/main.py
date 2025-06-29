from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .checkout.routes import router as checkout_router
from config import settings

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
app.include_router(checkout_router, prefix="/checkout", tags=["checkout"])

@app.get("/")
async def root():
    return {"message": "Welcome to Fastapi server"} 