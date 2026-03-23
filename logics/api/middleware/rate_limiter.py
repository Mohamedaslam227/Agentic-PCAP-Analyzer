import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from logics.data_layer.redis import RedisClient
from logics.api.core.config import settings

class RateLimiterMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        redis_client = RedisClient.get_client()
        client_ip = request.client.host
        path = request.url.path
        key = f"rate_limit:{client_ip}:{path}"
        current_time = int(time.time())
        window = settings.rate_limit_window
        limit = settings.rate_limit
        
        # Remove expired entries
        await redis_client.zremrangebyscore(key, 0, current_time - window)
        
        # Current request count
        current_count = await redis_client.zcard(key)
        if current_count >= limit:
            return JSONResponse(
                {"detail": "Rate limit exceeded. Try again later."},
                status_code=429,
                headers={"Retry-After": str(window)})
        await redis_client.zadd(key, {current_time: current_time})
        await redis_client.expire(key, window)
        return await call_next(request)
        