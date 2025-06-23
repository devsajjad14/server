from fastapi import APIRouter
from .schemas import HelloRequest, HelloResponse
from .services import get_hello_message, get_health_status

router = APIRouter()

@router.get("/", response_model=HelloResponse)
async def hello_world():
    """
    Simple hello world endpoint
    """
    request = HelloRequest()
    return await get_hello_message(request)

@router.post("/hello", response_model=HelloResponse)
async def hello_with_name(request: HelloRequest):
    """
    Hello endpoint that accepts a name
    """
    return await get_hello_message(request)

@router.get("/health", response_model=HelloResponse)
async def health_check():
    """
    Health check endpoint
    """
    return await get_health_status() 