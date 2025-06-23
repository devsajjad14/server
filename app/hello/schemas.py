from pydantic import BaseModel

class HelloRequest(BaseModel):
    name: str = "World"

class HelloResponse(BaseModel):
    message: str
    status: str = "success" 