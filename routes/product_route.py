"""
Product Route for Kepler Tech Conversational AI.
Handles product search and product specification queries
using the existing tool_executor infrastructure.
"""

import logging
from domain.conversation_types import LLMUnderstanding, RouteResult
from domain.conversation_state import ConversationState
from agent.tool_executor import catalog_tool_executor

logger = logging.getLogger("route:product")


def handle(understanding: LLMUnderstanding, state: ConversationState,
           raw_message: str = "") -> RouteResult:
    """Handle product search and product spec queries."""
    entities = understanding.entities
    model_code = entities.get("model_code")

    # ── Specific product spec query ──────────────────────────────────────
    if model_code:
        res = catalog_tool_executor.execute_tool(
            "get_product_specs", {"product_identifier": model_code}
        )
        if res.get("success"):
            product = res.get("product", {})
            cards = res.get("product_cards", [])
            state.active_product = product
            state.candidate_products = cards
            if not state.category:
                p_name_l = product.get("name", "").lower()
                if any(x in p_name_l for x in ["sc-t", "surecolor t", "cad", "plotter"]):
                    state.category = "technical_cad"
                elif any(x in p_name_l for x in ["sc-p", "surecolor p", "photo"]):
                    state.category = "photo_fine_art"
                elif any(x in p_name_l for x in ["workforce", "am-c", "copier"]):
                    state.category = "office_enterprise"
                elif any(x in p_name_l for x in ["ds-", "workforce ds", "scanner"]):
                    state.category = "scanner"
                elif any(x in p_name_l for x in ["cx-", "cy-"]):
                    state.category = "photo_booth"

            p_name = product.get("name", model_code)
            p_url = product.get("website_url") or product.get("web_url") or f"https://www.keplertechllc.com/product/{product.get('id', '')}/"
            return RouteResult(
                reply=f"Here are the verified specifications for [{p_name}]({p_url}):",
                product_cards=cards,
                source="tool:get_product_specs",
                needs_composition=False,
                evidence=[product],
            )

    # ── Product question on active product ───────────────────────────────
    if state.active_product and not model_code:
        product = state.active_product
        p_name = product.get("name", "")
        width = product.get("width", "")
        speed = product.get("speed", "")
        ink = product.get("ink_technology", "")
        
        reply_parts = [f"The {p_name} is an authorized system from Kepler Tech LLC."]
        if width:
            reply_parts.append(f"It supports print sizes up to {width}.")
        if speed:
            reply_parts.append(f"Print speed: {speed}.")
        if ink:
            reply_parts.append(f"Ink system: {ink}.")
        reply = " ".join(reply_parts)

        return RouteResult(
            reply=reply,
            product_cards=[],
            source="tool:get_product_specs",
            needs_composition=True,
            evidence=[product],
            instruction=f"Answer the customer's question about {p_name} using the verified specifications: width={width}, speed={speed}, ink={ink}.",
        )


    # ── Catalog search and Grounded Recommendation ──────────────────────
    from catalog.repository import catalog_repository
    from recommendation.eligibility import eligibility_engine
    from recommendation.ranker import product_ranker
    from recommendation.evidence_builder import build_recommendation_evidence

    # 1. Fetch category candidates
    all_cat_products = catalog_repository.get_by_category(state.category) if state.category else catalog_repository.get_all()
    if not all_cat_products:
        all_cat_products = catalog_repository.get_all()

    # 2. Hard Eligibility Filter
    eligible_assessments = eligibility_engine.filter_candidates(all_cat_products, state.requirements)

    # 3. Deterministic Python Ranking
    ranked_tuples = product_ranker.rank_candidates(eligible_assessments, state.requirements)

    if ranked_tuples:
        top_product, top_score, _ = ranked_tuples[0]
        state.active_product = top_product.to_dict()
        
        # Build cards
        cards = []
        for p, score, _ in ranked_tuples[:4]:
            cards.append(p.to_dict())
        state.candidate_products = cards

        # 4. Build Grounded Evidence Object
        evidence = [build_recommendation_evidence(top_product, state.requirements, top_score, ["print_size", "scan_required", "application"])]
        
        cat_name = state.category.replace("_", " ") if state.category else "equipment"
        top_url = top_product.source.website_url or f"https://www.keplertechllc.com/product/{top_product.id}/"
        reply = f"Here are the verified specifications for [{top_product.name}]({top_url}):"

        return RouteResult(
            reply=reply,
            product_cards=cards[:1] if len(cards) == 1 or not state.category else cards,
            source="recommendation:grounded_engine",
            needs_composition=False,
            evidence=evidence,
        )
    else:
        # Fallback if no product matched strictly
        search_terms = [raw_message or "printer"]
        query_str = " ".join(search_terms)
        search_res = catalog_tool_executor.execute_tool(
            "search_catalog",
            {"query": query_str, "limit": 4}
        )
        candidates = search_res.get("product_cards", [])
        state.candidate_products = candidates
        return RouteResult(
            reply="I couldn't find a product in our verified catalog that satisfies all those criteria simultaneously. Here are related options:",
            product_cards=candidates,
            source="tool:search_catalog",
        )

