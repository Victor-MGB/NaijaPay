from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Dict, Any
import json
import structlog
from ..repositories.idempotency_repo import IdempotencyRepository

logger = structlog.get_logger()

class IdempotencyMiddleware(BaseHTTPMiddleware):
    """Middleware to handle idempotency for POST requests"""
    
    def __init__(self, app):
        super().__init__(app)
        self.repo = IdempotencyRepository()
    
    async def dispatch(self, request: Request, call_next):
        # Only apply to POST/PUT/PATCH methods
        if request.method not in ["POST", "PUT", "PATCH"]:
            return await call_next(request)
        
        # Extract idempotency key from headers
        idempotency_key = request.headers.get("Idempotency-Key")
        
        if not idempotency_key:
            # For non-idempotent requests, proceed normally
            return await call_next(request)
        
        # Check if we've seen this key before
        cached_response = await self.repo.get_cached_response(idempotency_key)
        
        if cached_response:
            logger.info(f"Returning cached response for key: {idempotency_key}")
            return JSONResponse(
                status_code=cached_response.get("status_code", 200),
                content=cached_response.get("response_data")
            )
        
        # Process the request normally
        response = await call_next(request)
        
        # Only cache successful responses (2xx)
        if 200 <= response.status_code < 300:
            # Read response body
            response_body = b""
            async for chunk in response.body_iterator:
                response_body += chunk
            
            # Parse response data
            try:
                response_data = json.loads(response_body.decode())
                
                # Cache the response
                await self.repo.store_response(
                    idempotency_key=idempotency_key,
                    response_data=response_data,
                    status_code=response.status_code
                )
                
                # Return new response with same body
                return JSONResponse(
                    status_code=response.status_code,
                    content=response_data,
                    headers=dict(response.headers)
                )
            except Exception as e:
                logger.error(f"Failed to cache response: {e}")
                # Return original response
                return response
        
        return response