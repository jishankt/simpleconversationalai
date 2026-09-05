"""Response Composer for Kepler Tech Conversational AI.

Natural language composition is optional.  Deterministic/evidence-only route
results bypass the LLM.  When composition is allowed, numeric claims are
validated against the exact evidence supplied to the model.
"""

import json
import logging
from typing import Dict, Any, Optional

from domain.conversation_types import RouteResult, RouteName
from domain.conversation_state import ConversationState
from ollama_client import OllamaClient
from prompts.response_prompt import build_response_messages
from nlp.response_validator import validate_response
from agent.evidence_guard import numbers_are_grounded

logger = logging.getLogger("response_composer")


class ResponseComposer:
    def __init__(self, ollama_client: Optional[OllamaClient] = None):
        self.ollama_client = ollama_client

    def compose_response(
        self,
        customer_message: str,
        route_result: RouteResult,
        state: ConversationState,
        active_route: RouteName,
        model_name: Optional[str] = None,
    ) -> str:
        """Compose natural wording only when the route explicitly permits it."""
        if not route_result.reply:
            return ""

        # Critical anti-hallucination boundary.  Product/spec routes can return
        # deterministic evidence-only text with needs_composition=False.
        if getattr(route_result, "needs_composition", False) is False:
            return route_result.reply

        if (
            route_result.source.startswith("interceptor:")
            or route_result.source == "guardrail:price"
            or route_result.source == "guardrail:discount"
            or active_route == RouteName.BUSINESS_INFO
        ):
            return route_result.reply

        if not self.ollama_client:
            return route_result.reply

        evidence: Dict[str, Any] = {
            "route": active_route.value if hasattr(active_route, "value") else str(active_route),
            "base_response_template": route_result.reply,
            "product_count": len(route_result.product_cards),
        }

        if route_result.product_cards:
            evidence["top_products"] = [
                {
                    "name": p.get("name"),
                    "sku": p.get("sku"),
                    "category": p.get("category"),
                    "print_size_width": p.get("width"),
                    "speed": p.get("speed"),
                    "ink_technology": p.get("ink_technology"),
                    "features": (p.get("features") or [])[:3] if isinstance(p.get("features") or [], list) else p.get("features"),
                    "intended_use": p.get("intended_usage") or p.get("intended_use") or (p.get("description") or "")[:250],
                }
                for p in route_result.product_cards[:3]
            ]

        if route_result.evidence:
            evidence["detailed_evidence"] = route_result.evidence

        if route_result.consumable_cards:
            evidence["consumables"] = [
                {"name": c.get("name"), "type": c.get("type")}
                for c in route_result.consumable_cards[:4]
            ]

        messages = build_response_messages(
            customer_message=customer_message,
            evidence=evidence,
            recent_turns=state.history_turns[-4:] if state.history_turns else [],
            customer_name=state.customer_name,
            qualification_question=state.pending_question,
        )

        try:
            comp_res = self.ollama_client.compose(messages=messages, model=model_name)
            if comp_res.get("success") and comp_res.get("response"):
                composed_text = comp_res["response"].strip()
                val = validate_response(
                    response=composed_text,
                    previous_response=state.last_assistant_response,
                    context_intent=state.last_intent,
                )

                # A newly invented number is a hard failure even if the normal
                # conversational validator considers the prose acceptable.
                evidence_text = json.dumps(evidence, ensure_ascii=False, default=str)
                numeric_ok = numbers_are_grounded(composed_text, evidence_text)

                if val.valid and numeric_ok:
                    logger.info("Composed natural reply via LLM with grounded numeric claims")
                    return val.sanitized_response

                if not numeric_ok:
                    logger.warning("LLM composition introduced unsupported numeric claim; using deterministic fallback")
                else:
                    logger.warning("Composed reply failed validation: %s", val.violations)
        except Exception as e:
            logger.warning("Error during response composition: %s. Falling back to template.", e)

        return route_result.reply
