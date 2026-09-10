"""
Product Catalog & Requirement Specialist Agent (Agent 2).
Handles accurate product fetching by model or customer requirements,
qualification workflow, and ink/media consumable matching.
"""

import logging
from typing import Dict, Any, List, Optional
from domain.conversation_types import RouteName, LLMUnderstanding, RouteResult
from domain.conversation_state import ConversationState
from agents.base_agent import BaseSpecialistAgent
from routes import product_route, qualification_route, consumables_route

logger = logging.getLogger("agent.product_catalog")


class ProductCatalogAgent(BaseSpecialistAgent):
    def __init__(self):
        super().__init__(
            agent_id="product_specialist",
            name="Product & Catalog Specialist",
            role="Catalog & Requirement Matching",
            theme_color="#1877f2",
            badge="🖨️ Product Specialist",
            icon="fas fa-print",
        )

    def handle_turn(
        self,
        raw_message: str,
        normalized_message: str,
        understanding: Optional[LLMUnderstanding],
        state: ConversationState,
        **kwargs,
    ) -> RouteResult:
        logger.info(f"ProductCatalogAgent handling message: {normalized_message[:60]}")
        route = kwargs.get("route")

        # 1. Consumables
        if route == RouteName.CONSUMABLES or (understanding and understanding.intent.value == "consumable_inquiry"):
            res = consumables_route.handle(understanding, state, raw_message=normalized_message)
            res.source = "agent:product_specialist:consumables"
            return res

        # 2. Qualification
        if route == RouteName.QUALIFICATION or state.stage == "qualifying":
            res = qualification_route.handle(understanding, state, raw_message=normalized_message)
            if res.reply == "__READY_FOR_SEARCH__":
                res = product_route.handle(understanding, state, raw_message=normalized_message)
                res.source = "agent:product_specialist:qualified_search"
            else:
                res.source = "agent:product_specialist:qualification"
            return res

        # 3. Direct product lookup or general catalog search
        res = product_route.handle(understanding, state, raw_message=normalized_message)
        res.source = "agent:product_specialist:catalog"
        return res


product_catalog_agent = ProductCatalogAgent()
