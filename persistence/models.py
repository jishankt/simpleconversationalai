"""
Persistence Models and Table Definitions for Kepler Tech Conversational AI.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import time


@dataclass
class SessionRecord:
    session_id: str
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    customer_name: Optional[str] = None
    state_json: str = "{}"
    history_json: str = "[]"


CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS conversation_sessions (
    session_id TEXT PRIMARY KEY,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    customer_name TEXT,
    state_json TEXT NOT NULL,
    history_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessions_updated ON conversation_sessions (updated_at);
"""
