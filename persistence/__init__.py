"""
Persistence layer for Kepler Tech Conversational AI.
Provides SQLite-backed persistence for conversation states and histories.
"""

from persistence.state_repository import StateRepository, state_repository

__all__ = ["StateRepository", "state_repository"]
