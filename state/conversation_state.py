"""
Canonical Conversation State — Backward Compatibility Layer.

This module re-exports the enhanced ConversationState as CanonicalState
so that all existing imports (from state.conversation_state import CanonicalState)
continue to work without modification during the incremental migration.
"""
from domain.conversation_state import ConversationState as CanonicalState

__all__ = ["CanonicalState"]
