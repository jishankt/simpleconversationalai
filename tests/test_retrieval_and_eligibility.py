"""
Unit tests for Retrieval Integrity and Strict Eligibility.
Verifies:
1. Exact corpus spec joining (no cross-contamination across printers).
2. Threshold confidence gating (rejects low-confidence false positives).
3. Strict eligibility conflict handling (mutually conflicting requirements return 0 cards with trade-offs).
"""
import unittest
from rag.retriever import rag_retriever, UNKNOWN_QUERY_THRESHOLD
from routes.product_route import handle_product_recommendation
from domain.conversation_state import ConversationState


class TestRetrievalAndEligibility(unittest.TestCase):
    def test_corpus_spec_isolation(self):
        """Ensure specs from SC-T3100 (24-inch, no scanner) do not leak into T5400M or vice versa."""
        t3100_products = [p for p in rag_retriever.products if "t3100" in p.get("name", "").lower() and "t5" not in p.get("name", "").lower()]
        self.assertTrue(len(t3100_products) > 0)
        t3100 = t3100_products[0]

        # T3100 is 24-inch, NOT 36-inch
        self.assertIn("24-inch", t3100.get("width", ""))
        self.assertNotIn("36-inch", t3100.get("width", ""))

    def test_confidence_threshold_gating(self):
        """Ensure random queries or non-printer strings return empty or low confidence."""
        gibberish = "xyzzy qux foo bar nonexistent quantum widget 99999"
        results = rag_retriever.retrieve(gibberish, top_k=5)
        # Should return empty list because scores fall below UNKNOWN_QUERY_THRESHOLD
        self.assertEqual(len(results), 0)

    def test_strict_eligibility_conflict_handling(self):
        """
        When requirements are mutually exclusive or cannot be satisfied,
        the system must return 0 product cards, state the conflict clearly,
        and provide trade-off options rather than dumping irrelevant products.
        """
        state = ConversationState(session_id="test-conflict-ses")
        state.category = "technical_cad"
        # Request an impossible combination in current catalog:
        # e.g. 17-inch CAD plotter with 600 dpi scanner
        state.requirements = {
            "category": "technical_cad",
            "print_size": "17-inch",
            "scan_required": True
        }

        from domain.conversation_types import LLMUnderstanding, Intent

        understanding = LLMUnderstanding(
            intent=Intent.PRODUCT_DISCOVERY,
            confidence=0.95,
            requested_action="recommend_product",
            entities={"category": "technical_cad"}
        )

        result = handle_product_recommendation(
            understanding=understanding,
            state=state,
            raw_message="I need a 17-inch CAD plotter with built-in scanner"
        )

        # Strict zero-card policy on hard eligibility conflict
        self.assertEqual(len(result.product_cards), 0)
        reply_lower = result.reply.lower()
        self.assertTrue(
            "conflict" in reply_lower or "trade-off" in reply_lower or "compromise" in reply_lower or "couldn't find" in reply_lower or "could not find" in reply_lower or "options" in reply_lower
        )


if __name__ == "__main__":
    unittest.main()
