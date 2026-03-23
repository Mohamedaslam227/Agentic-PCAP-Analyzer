import json
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from logics.api.core.config import settings


class RequestValidationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > settings.max_request_size:
            return JSONResponse(status_code=413, content={"detail": "Request too large"})

        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        request.state.request_id = request_id

        if request.headers.get("content-type", "").startswith("application/json"):
            body = await request.body()
            if body:
                try:
                    json.loads(body)
                except json.JSONDecodeError:
                    return JSONResponse(status_code=400, content={"detail": "Invalid JSON body"})

        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        return response
