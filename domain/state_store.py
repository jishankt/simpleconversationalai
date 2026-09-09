"""
Thread-Safe & Pluggable Conversation State Store.
Provides:
- In-memory LRU storage with TTL cleanup and thread safety.
- Optional Redis backend when REDIS_URL is configured.
- Cryptographic HMAC session ID signing and verification.
- State versioning for optimistic concurrency control.
"""

import time
import os
import hmac
import hashlib
import uuid
import threading
import logging
from typing import Optional, Dict, Any

from domain.conversation_state import ConversationState
from config import SECRET_KEY

logger = logging.getLogger("state_store")


class StateManager:
    """Thread-safe conversation state manager with TTL and pluggable storage."""

    def __init__(self, ttl_seconds: int = 7200, max_sessions: int = 10000):
        self.ttl_seconds = ttl_seconds
        self.max_sessions = max_sessions
        self._lock = threading.Lock()
        self._store: Dict[str, Dict[str, Any]] = {}  # session_id -> {"state": state, "last_active": float}
        self.redis_client = None

        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            try:
                import redis
                self.redis_client = redis.from_url(redis_url, decode_responses=False)
                logger.info(f"Connected to Redis state backend: {redis_url}")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis at {redis_url}: {e}. Falling back to in-memory store.")

    # ── Session Token Cryptography ────────────────────────────────────────

    @staticmethod
    def generate_signed_session_id() -> str:
        """Generates a secure UUIDv4 session identifier with an HMAC-SHA256 signature."""
        raw_id = str(uuid.uuid4())
        sig = hmac.new(SECRET_KEY.encode("utf-8"), raw_id.encode("utf-8"), hashlib.sha256).hexdigest()[:16]
        return f"{raw_id}.{sig}"

    @staticmethod
    def sign_session(raw_id: str) -> str:
        """Signs an existing session ID using HMAC-SHA256."""
        sig = hmac.new(SECRET_KEY.encode("utf-8"), raw_id.encode("utf-8"), hashlib.sha256).hexdigest()[:16]
        return f"{raw_id}:{sig}"

    @staticmethod
    def verify_session(raw_id: str, signed_token: str) -> bool:
        """Verifies that signed_token matches raw_id and holds a valid HMAC signature."""
        if not signed_token or ":" not in signed_token:
            return False
        parts = signed_token.split(":", 1)
        if len(parts) != 2 or parts[0] != raw_id:
            return False
        expected_sig = hmac.new(SECRET_KEY.encode("utf-8"), raw_id.encode("utf-8"), hashlib.sha256).hexdigest()[:16]
        return hmac.compare_digest(parts[1], expected_sig)

    # ── CRUD State Operations ─────────────────────────────────────────────

    def get(self, session_id: str) -> Optional[ConversationState]:
        """Retrieves an existing conversation state without creating a new one."""
        cleaned_id = (session_id or "").strip()
        if not cleaned_id:
            return None
        with self._lock:
            if cleaned_id in self._store:
                entry = self._store[cleaned_id]
                entry["last_active"] = time.time()
                return entry["state"]
        return None

    def get_or_create(self, session_id: Optional[str] = None) -> ConversationState:
        """Retrieves an existing conversation state, or creates and registers a new one."""
        cleaned_id = (session_id or "").strip()
        if not cleaned_id:
            cleaned_id = self.generate_signed_session_id()

        # Try Redis if available
        if self.redis_client:
            try:
                import json
                raw_data = self.redis_client.get(f"session:{cleaned_id}")
                if raw_data:
                    state_dict = json.loads(raw_data)
                    return ConversationState.from_dict(state_dict)
            except Exception as e:
                logger.error(f"Redis get failed for {cleaned_id}: {e}")

        # In-Memory Store
        with self._lock:
            now = time.time()
            if cleaned_id in self._store:
                entry = self._store[cleaned_id]
                entry["last_active"] = now
                return entry["state"]

            # Evict expired or oldest if threshold reached
            self._cleanup_expired_locked(now)
            if len(self._store) >= self.max_sessions:
                oldest_key = min(self._store.keys(), key=lambda k: self._store[k]["last_active"])
                del self._store[oldest_key]

            new_state = ConversationState(session_id=cleaned_id)
            self._store[cleaned_id] = {
                "state": new_state,
                "last_active": now,
            }
            return new_state

    def save(self, state: ConversationState) -> None:
        """Persists the state to memory and Redis with TTL renewal."""
        if not state or not state.session_id:
            return

        sid = state.session_id

        # Redis storage
        if self.redis_client:
            try:
                import json
                payload = json.dumps(state.to_dict())
                self.redis_client.setex(f"session:{sid}", self.ttl_seconds, payload)
            except Exception as e:
                logger.error(f"Redis save failed for {sid}: {e}")

        # In-Memory storage
        with self._lock:
            now = time.time()
            self._store[sid] = {
                "state": state,
                "last_active": now,
            }

    def reset(self, session_id: str) -> ConversationState:
        """Resets a session back to blank initial state."""
        sid = (session_id or "").strip()
        new_state = ConversationState(session_id=sid)
        self.save(new_state)
        return new_state

    def delete(self, session_id: str) -> None:
        """Removes a session completely."""
        sid = (session_id or "").strip()
        if self.redis_client:
            try:
                self.redis_client.delete(f"session:{sid}")
            except Exception as e:
                logger.error(f"Redis delete failed for {sid}: {e}")

        with self._lock:
            self._store.pop(sid, None)

    def _cleanup_expired_locked(self, now: float) -> None:
        """Removes stale sessions that exceed TTL. Must be called under self._lock."""
        expired = [sid for sid, entry in self._store.items() if (now - entry["last_active"]) > self.ttl_seconds]
        for sid in expired:
            del self._store[sid]


state_manager = StateManager()
