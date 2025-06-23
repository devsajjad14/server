from .schemas import HelloRequest, HelloResponse

async def get_hello_message(request: HelloRequest) -> HelloResponse:
    """
    Business logic for generating hello message
    """
    message = f"Hello, {request.name}!"
    return HelloResponse(message=message)

async def get_health_status() -> HelloResponse:
    """
    Health check service
    """
    return HelloResponse(message="Server is running!", status="healthy") 