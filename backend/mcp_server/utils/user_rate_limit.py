"""User-based rate limiting implementation."""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from typing import Optional

from fastapi import HTTPException, Request, status
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded


class UserRateLimiter:
    """User-based rate limiter with sliding window algorithm."""
    
    def __init__(
        self,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
        burst_limit: int = 10,
    ):
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.burst_limit = burst_limit
        
        # Sliding window storage: user_id -> deque of timestamps
        self.minute_windows: dict[str, deque[float]] = defaultdict(deque)
        self.hour_windows: dict[str, deque[float]] = defaultdict(deque)
        self.burst_windows: dict[str, deque[float]] = defaultdict(deque)
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
    
    async def is_allowed(self, user_id: str) -> tuple[bool, dict[str, int]]:
        """Check if user is allowed to make request."""
        async with self._lock:
            now = time.time()
            
            # Clean old entries and check limits
            minute_count = self._clean_and_count(
                self.minute_windows[user_id], now, 60
            )
            hour_count = self._clean_and_count(
                self.hour_windows[user_id], now, 3600
            )
            burst_count = self._clean_and_count(
                self.burst_windows[user_id], now, 10
            )
            
            # Check limits
            if burst_count >= self.burst_limit:
                return False, {
                    "limit_type": "burst",
                    "limit": self.burst_limit,
                    "current": burst_count,
                    "reset_in": 10,
                }
            
            if minute_count >= self.requests_per_minute:
                return False, {
                    "limit_type": "minute",
                    "limit": self.requests_per_minute,
                    "current": minute_count,
                    "reset_in": 60,
                }
            
            if hour_count >= self.requests_per_hour:
                return False, {
                    "limit_type": "hour",
                    "limit": self.requests_per_hour,
                    "current": hour_count,
                    "reset_in": 3600,
                }
            
            # Record the request
            self.minute_windows[user_id].append(now)
            self.hour_windows[user_id].append(now)
            self.burst_windows[user_id].append(now)
            
            return True, {
                "minute_remaining": self.requests_per_minute - minute_count - 1,
                "hour_remaining": self.requests_per_hour - hour_count - 1,
                "burst_remaining": self.burst_limit - burst_count - 1,
            }
    
    def _clean_and_count(self, window: deque[float], now: float, window_size: int) -> int:
        """Clean old entries and return current count."""
        cutoff = now - window_size
        
        # Remove old entries
        while window and window[0] < cutoff:
            window.popleft()
        
        return len(window)


class UserRateLimitMiddleware:
    """Middleware for user-based rate limiting."""
    
    def __init__(self, limiter: UserRateLimiter):
        self.limiter = limiter
    
    async def __call__(self, request: Request, call_next):
        """Apply rate limiting based on user ID."""
        # Extract user ID from request
        user_id = await self._extract_user_id(request)
        
        if user_id:
            allowed, info = await self.limiter.is_allowed(user_id)
            
            if not allowed:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "error": "Rate limit exceeded",
                        "limit_info": info,
                        "user_id": user_id,
                    },
                    headers={
                        "Retry-After": str(info.get("reset_in", 60)),
                        "X-RateLimit-Limit": str(info.get("limit", 0)),
                        "X-RateLimit-Remaining": str(info.get("current", 0)),
                    }
                )
            
            # Add rate limit headers to response
            response = await call_next(request)
            response.headers["X-RateLimit-Minute-Remaining"] = str(
                info.get("minute_remaining", 0)
            )
            response.headers["X-RateLimit-Hour-Remaining"] = str(
                info.get("hour_remaining", 0)
            )
            return response
        
        # No user ID, proceed without rate limiting
        return await call_next(request)
    
    async def _extract_user_id(self, request: Request) -> Optional[str]:
        """Extract user ID from request."""
        # Try JWT token first
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
            try:
                # Decode JWT to get user ID
                import jwt
                payload = jwt.decode(token, options={"verify_signature": False})
                return payload.get("sub") or payload.get("user_id")
            except Exception:
                pass
        
        # Try API key
        api_key = request.headers.get("x-api-key")
        if api_key:
            # Hash API key to create consistent user ID
            import hashlib
            return hashlib.sha256(api_key.encode()).hexdigest()[:16]
        
        # Fallback to IP address for anonymous users
        client_ip = request.client.host if request.client else "unknown"
        return f"ip:{client_ip}"


# Global rate limiter
_user_limiter: Optional[UserRateLimiter] = None


def get_user_limiter() -> UserRateLimiter:
    """Get global user rate limiter."""
    global _user_limiter
    if _user_limiter is None:
        _user_limiter = UserRateLimiter()
    return _user_limiter


def init_user_rate_limiting(
    requests_per_minute: int = 60,
    requests_per_hour: int = 1000,
    burst_limit: int = 10,
) -> UserRateLimiter:
    """Initialize user-based rate limiting."""
    global _user_limiter
    _user_limiter = UserRateLimiter(
        requests_per_minute=requests_per_minute,
        requests_per_hour=requests_per_hour,
        burst_limit=burst_limit,
    )
    return _user_limiter
