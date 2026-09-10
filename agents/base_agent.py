"""
Base Specialist Agent for Kepler Tech Conversational AI.
Defines common interface and metadata for specialized sub-agents.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from domain.conversation_types import LLMUnderstanding, RouteResult
from domain.conversation_state import ConversationState


class BaseSpecialistAgent(ABC):
    def __init__(
        self,
        agent_id: str,
        name: str,
        role: str,
        theme_color: str,
        badge: str,
        icon: str,
    ):
        self.agent_id = agent_id
        self.name = name
        self.role = role
        self.theme_color = theme_color
        self.badge = badge
        self.icon = icon

    def get_info(self) -> Dict[str, str]:
        """Returns visual and operational metadata for frontend theming and routing."""
        return {
            "id": self.agent_id,
            "name": self.name,
            "role": self.role,
            "theme_color": self.theme_color,
            "badge": self.badge,
            "icon": self.icon,
        }

    @abstractmethod
    def handle_turn(
        self,
        raw_message: str,
        normalized_message: str,
        understanding: Optional[LLMUnderstanding],
        state: ConversationState,
        **kwargs,
    ) -> RouteResult:
        """Processes the turn for this specialist's domain."""
        pass
