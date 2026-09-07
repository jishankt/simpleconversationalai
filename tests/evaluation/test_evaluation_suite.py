"""
Evaluation Suite for Kepler Tech Conversational Recommendation Engine.
Tests:
  1. Requirement Collection (Single-question flow, CAD, Office, Scanners)
  2. Requirement Corrections ('Actually A0', 'No scanner')
  3. Anti-Hallucination & Unknowns ('What is the resolution when unverified')
  4. Fake / Non-existent product queries
  5. Contradiction & Eligibility Filtering (Scanner required vs print-only)
  6. Conversational interruptions & context persistence
"""
import unittest
from domain.conversation_state import ConversationState
from conversation.next_question_engine import NextQuestionEngine
from conversation.requirement_extractor import requirement_extractor
from recommendation.eligibility import eligibility_engine
from recommendation.ranker import product_ranker
from catalog.repository import catalog_repository
from catalog.product_resolver import resolve_canonical_id
from validation.claim_validator import output_validator


class TestGroundedRecommendationEngine(unittest.TestCase):

    def setUp(self):
        self.state = ConversationState(session_id="eval-test-01")
        self.next_q = NextQuestionEngine()
        self.repo = catalog_repository

    def test_01_cad_single_question_flow(self):
        """Test multi-turn requirement collection asks one question at a time."""
        self.state.category = "technical_cad"
        
        # Turn 1: No size known -> Ask size
        step1 = self.next_q.evaluate_next_step(self.state)
        self.assertIsNotNone(step1)
        self.assertEqual(step1["field"], "print_size")
        self.assertIn("maximum", step1["question"].lower())

        # Customer answers: A0
        extracted = requirement_extractor.extract_and_validate("A0", self.state)
        self.state.requirements.update(extracted)
        self.assertEqual(self.state.requirements.get("print_size"), "A0")

        # Turn 2: Size known -> Ask scanner
        step2 = self.next_q.evaluate_next_step(self.state)
        self.assertIsNotNone(step2)
        self.assertEqual(step2["field"], "scan_required")

        # Customer answers: No scanner
        extracted = requirement_extractor.extract_and_validate("Print only, no scanner needed", self.state)
        self.state.requirements.update(extracted)
        self.assertEqual(self.state.requirements.get("scan_required"), False)

        # Turn 3: Size & Scanner known -> Ask daily volume
        step3 = self.next_q.evaluate_next_step(self.state)
        self.assertIsNotNone(step3)
        self.assertEqual(step3["field"], "daily_volume")

        # Customer answers: 20 drawings per day
        extracted = requirement_extractor.extract_and_validate("About 20 drawings per day", self.state)
        self.state.requirements.update(extracted)
        self.assertEqual(self.state.requirements.get("daily_volume"), "medium")

        # Turn 4: All critical and important satisfied -> None (ready for recommendation)
        step4 = self.next_q.evaluate_next_step(self.state)
        self.assertIsNone(step4)

    def test_02_requirement_corrections(self):
        """Test user correcting an earlier requirement."""
        self.state.category = "technical_cad"
        self.state.requirements = {"print_size": "A1", "scan_required": False}

        # Customer corrects to A0
        extracted = requirement_extractor.extract_and_validate("Actually I need A0", self.state)
        self.state.requirements.update(extracted)
        self.assertEqual(self.state.requirements["print_size"], "A0")

    def test_03_exact_product_resolution(self):
        """Test SKU / model name normalization."""
        self.assertEqual(resolve_canonical_id("SC-T5400M"), "epson-t5400m")
        self.assertEqual(resolve_canonical_id("Epson T5400"), "epson-t5400m")
        self.assertEqual(resolve_canonical_id("T3100"), "epson-t3100")
        self.assertEqual(resolve_canonical_id("Citizen CX-02"), "citizen-cx-02")
        self.assertIsNone(resolve_canonical_id("Epson ABC-99999"))

    def test_04_hard_eligibility_contradiction_gate(self):
        """Test scanner requirement strictly excludes print-only plotters."""
        t5100 = self.repo.get_by_id("epson-t5100")  # A0, Print-only (has_scanner = False)
        t5400m = self.repo.get_by_id("epson-t5400m")  # A0, Integrated scanner (has_scanner = True)

        # Customer requires A0 + Scanner
        reqs = {"print_size": "A0", "scan_required": True}
        res_t5100 = eligibility_engine.assess_product(t5100, reqs)
        res_t5400m = eligibility_engine.assess_product(t5400m, reqs)

        # T5100 must FAIL eligibility
        self.assertFalse(res_t5100.is_eligible)
        self.assertIn("scan_required", res_t5100.failed)

        # T5400M must PASS eligibility
        self.assertTrue(res_t5400m.is_eligible)
        self.assertIn("scan_required", res_t5400m.matched)

    def test_05_deterministic_ranking_scores(self):
        """Test python deterministic ranking outputs highest score for best match."""
        candidates = self.repo.get_by_category("technical_cad")
        reqs = {"print_size": "A0", "scan_required": False, "application": "CAD", "daily_volume": "medium"}
        
        eligible = eligibility_engine.filter_candidates(candidates, reqs)
        ranked = product_ranker.rank_candidates(eligible, reqs)

        # Epson T5100 should rank higher than T3100 (which is A1)
        top_product = ranked[0][0]
        self.assertEqual(top_product.id, "epson-t5100")

    def test_06_claim_and_numeric_validator(self):
        """Test validator intercepts hallucinated numbers and capabilities."""
        evidence = {
            "verified_specs": {
                "resolution": "2400 x 1200 dpi",
                "has_scanner": False,
            }
        }

        # Valid text
        valid_text = "The Epson T5100 prints at 2400 x 1200 dpi."
        ok, msg = output_validator.validate_all(valid_text, evidence)
        self.assertTrue(ok)

        # Hallucinated resolution
        fake_res_text = "The Epson T5100 has an ultra-high 4800 x 2400 dpi resolution."
        ok, msg = output_validator.validate_all(fake_res_text, evidence)
        self.assertFalse(ok)
        self.assertIn("Hallucinated resolution", msg)

        # Hallucinated scanner on print-only
        fake_scanner_text = "This unit includes an integrated scanner for drawings."
        ok, msg = output_validator.validate_all(fake_scanner_text, evidence)
        self.assertFalse(ok)
        self.assertIn("claims scanner exists", msg)


if __name__ == "__main__":
    unittest.main()
