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


@dataclass
class LeadRecord:
    lead_id: Optional[int] = None
    session_id: str = ""
    created_at: float = field(default_factory=time.time)
    customer_name: Optional[str] = None
    company: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    product_interest: Optional[str] = None
    notes: Optional[str] = None


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

CREATE TABLE IF NOT EXISTS commercial_leads (
    lead_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    created_at REAL NOT NULL,
    customer_name TEXT,
    company TEXT,
    email TEXT,
    phone TEXT,
    product_interest TEXT,
    notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_leads_session ON commercial_leads (session_id);
CREATE INDEX IF NOT EXISTS idx_leads_created ON commercial_leads (created_at);
"""
