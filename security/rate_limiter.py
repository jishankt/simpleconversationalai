"""
Rate Limiter & Client IP Resolver for Kepler Tech SalesAI.

Provides:
- Secure client IP extraction supporting Cloudflare (CF-Connecting-IP) and reverse proxies (Nginx),
  without blindly trusting spoofed X-Forwarded-For headers.
- Thread-safe sliding-window rate limiting per-IP and per-session.
- Standard HTTP 429 response structure with Retry-After header.
"""

import time
import re
import threading
from typing import Tuple, Optional, Dict, List
from config import (
    RATE_LIMIT_ENABLED,
    RATE_LIMIT_IP_PER_MINUTE,
    RATE_LIMIT_SESSION_PER_MINUTE,
    TRUSTED_PROXY_COUNT,
    TRUST_CF_CONNECTING_IP,
)

# Regex for IPv4 and IPv6 validation
IPV4_REGEX = re.compile(r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$")
IPV6_REGEX = re.compile(r"^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$|^::$|^::1$|^([0-9a-fA-F]{1,4}:)+:[0-9a-fA-F]{1,4}$")


def is_valid_ip(ip: str) -> bool:
    """Validates whether string is a valid IPv4 or IPv6 address."""
    if not ip or not isinstance(ip, str):
        return False
    clean_ip = ip.strip()
    return bool(IPV4_REGEX.match(clean_ip) or IPV6_REGEX.match(clean_ip))


def get_client_ip(request) -> str:
    """
    Deterministically resolves the real client IP address.

    Security Rules:
    1. If TRUST_CF_CONNECTING_IP is True, inspect CF-Connecting-IP first (validated).
    2. If TRUSTED_PROXY_COUNT > 0, inspect X-Forwarded-For from the right, taking
       the entry corresponding to the first trusted proxy's perspective.
       Never blindly trust the leftmost X-Forwarded-For value as clients can easily spoof it.
    3. Fallback safely to request.remote_addr.
    """
    # 1. Cloudflare header
    if TRUST_CF_CONNECTING_IP:
        cf_ip = request.headers.get("CF-Connecting-IP")
        if cf_ip and is_valid_ip(cf_ip):
            return cf_ip.strip()

    # 2. X-Forwarded-For with trusted proxy hop index
    xff = request.headers.get("X-Forwarded-For")
    if xff and TRUSTED_PROXY_COUNT > 0:
        parts = [p.strip() for p in xff.split(",") if p.strip()]
        if len(parts) >= TRUSTED_PROXY_COUNT:
            candidate = parts[-TRUSTED_PROXY_COUNT]
            if is_valid_ip(candidate):
                return candidate

    # 3. Direct remote address fallback
    remote = request.remote_addr
    if remote and is_valid_ip(remote):
        return remote.strip()

    return "127.0.0.1"


class SlidingWindowRateLimiter:
    """Thread-safe sliding-window rate limiter."""

    def __init__(self):
        self._storage: Dict[str, List[float]] = {}
        self._lock = threading.Lock()

    def is_allowed(self, key: str, limit: int, window_seconds: int = 60) -> Tuple[bool, int]:
        """
        Determines if a request under `key` is permitted within the sliding window.
        Returns:
            (is_allowed: bool, retry_after: int)
        """
        if limit <= 0:
            return True, 0

        now = time.time()
        cutoff = now - window_seconds

        with self._lock:
            timestamps = self._storage.get(key, [])
            # Evict timestamps outside the window
            timestamps = [ts for ts in timestamps if ts > cutoff]

            if len(timestamps) >= limit:
                oldest = timestamps[0]
                retry_after = max(1, int(window_seconds - (now - oldest)))
                self._storage[key] = timestamps
                return False, retry_after

            timestamps.append(now)
            self._storage[key] = timestamps
            return True, 0

    def check_request(self, ip: str, session_id: Optional[str] = None) -> Tuple[bool, Optional[str], int]:
        """
        Validates both IP and session limits for an incoming request.
        Returns:
            (allowed: bool, error_message: Optional[str], retry_after: int)
        """
        if not RATE_LIMIT_ENABLED:
            return True, None, 0

        # IP check
        ip_allowed, retry_after = self.is_allowed(f"ip:{ip}", RATE_LIMIT_IP_PER_MINUTE, 60)
        if not ip_allowed:
            return False, f"Too many requests from this IP address. Please wait {retry_after} seconds.", retry_after

        # Session check (if session_id provided)
        if session_id:
            sess_allowed, retry_after = self.is_allowed(f"session:{session_id}", RATE_LIMIT_SESSION_PER_MINUTE, 60)
            if not sess_allowed:
                return False, f"Too many requests for this conversation session. Please wait {retry_after} seconds.", retry_after

        return True, None, 0

    def reset(self):
        """Resets all tracked rate limit buckets (used in test fixtures)."""
        with self._lock:
            self._storage.clear()


rate_limiter = SlidingWindowRateLimiter()
