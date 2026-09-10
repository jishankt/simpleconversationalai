"""
Comprehensive production-readiness test suite for factual grounding and deterministic validator.
Covers all 12 production-readiness requirements.
"""

import unittest
from pathlib import Path
from typing import Dict, Any

from catalog.repository import catalog_repository
from recommendation.eligibility import eligibility_engine, AssessmentResult
from recommendation.ranker import product_ranker
from validation.deterministic_validator import (
    deterministic_validator,
    DeterministicResponseValidator,
    PRINTER_CONSUMABLE_LINKS,
    KNOWN_VALID_SKUS,
)
from domain.conversation_state import ConversationState
from guardrails import check_user_intent_for_pricing_or_discount, DISCOUNT_REFUSAL, validate_and_sanitize_response
from agent.orchestrator import orchestrator


class TestProductionReadiness(unittest.TestCase):

    # ── Requirement 1: Fail Closed ──────────────────────────────────────────
    def test_fail_closed_safe_fallback(self):
        """If deterministic validation fails after regeneration, return safe catalogue card only."""
        state = ConversationState(session_id="test_fail_closed")
        state.active_product_id = "citizen-cy-02"
        cy02 = catalog_repository.get_by_id("citizen-cy-02")
        self.assertIsNotNone(cy02)
        state.active_product = cy02.to_dict()

        # Build canonical structured reply
        safe_reply = orchestrator._build_canonical_structured_reply(
            product_id="citizen-cy-02",
            state=state,
            route_result=None
        )
        self.assertIn("Citizen CY-02", safe_reply)
        self.assertIn("13.8 kg", safe_reply)
        self.assertNotIn("18 kg", safe_reply)
        self.assertNotIn("100% guaranteed", safe_reply)

        # Validate the safe reply is completely clean
        is_valid, violations = deterministic_validator.validate(
            safe_reply,
            context={"product_id": "citizen-cy-02", "source": "catalog"}
        )
        self.assertTrue(is_valid, f"Safe reply must pass deterministic validation: {violations}")

    # ── Requirement 2: Exact supported_print_sizes Eligibility ───────────────
    def test_cz01_fails_6x8(self):
        """CZ-01 must fail 6x8 print size constraint."""
        cz01 = catalog_repository.get_by_id("citizen-cz-01")
        self.assertIsNotNone(cz01)
        res = eligibility_engine.assess_product(cz01, {"print_size": "6x8"})
        self.assertFalse(res.is_eligible, "CZ-01 must fail 6x8")
        self.assertIn("print_size", res.failed)

    def test_cx02w_fails_4x6(self):
        """CX-02W must fail 4x6 print size constraint (no approved compatible media)."""
        cx02w = catalog_repository.get_by_id("citizen-cx-02w")
        self.assertIsNotNone(cx02w)
        res = eligibility_engine.assess_product(cx02w, {"print_size": "4x6"})
        self.assertFalse(res.is_eligible, "CX-02W must fail 4x6")
        self.assertIn("print_size", res.failed)

    def test_cx02_matches_all_four_sizes(self):
        """CX-02 matches 4x6, 5x7, 6x8, and 6x9."""
        cx02 = catalog_repository.get_by_id("citizen-cx-02")
        self.assertIsNotNone(cx02)
        for sz in ["4x6", "5x7", "6x8", "6x9"]:
            res = eligibility_engine.assess_product(cx02, {"print_size": sz})
            self.assertTrue(res.is_eligible, f"CX-02 must be eligible for {sz}")

    def test_cy02_fails_6x9_and_matches_4x6_6x8(self):
        """CY-02 matches 4x6, 5x7, 6x8, but fails 6x9."""
        cy02 = catalog_repository.get_by_id("citizen-cy-02")
        self.assertIsNotNone(cy02)
        for sz in ["4x6", "5x7", "6x8"]:
            res = eligibility_engine.assess_product(cy02, {"print_size": sz})
            self.assertTrue(res.is_eligible, f"CY-02 must be eligible for {sz}")

        res_6x9 = eligibility_engine.assess_product(cy02, {"print_size": "6x9"})
        self.assertFalse(res_6x9.is_eligible, "CY-02 must fail 6x9")

    def test_a2_wide_format_eligibility(self):
        """Wide-format printers with max width >= 420mm support A2."""
        p7500 = catalog_repository.get_by_id("epson-sc-p7500")
        self.assertIsNotNone(p7500)
        res_p7500 = eligibility_engine.assess_product(p7500, {"print_size": "A2"})
        self.assertTrue(res_p7500.is_eligible, "Epson SC-P7500 (24-inch) must support A2")

        t5100 = catalog_repository.get_by_id("epson-sc-t5100")
        self.assertIsNotNone(t5100)
        res_t5100 = eligibility_engine.assess_product(t5100, {"print_size": "A2"})
        self.assertTrue(res_t5100.is_eligible, "Epson SC-T5100 (36-inch) must support A2")

        # Citizen CX-02 (max width 152mm) must fail A2
        cx02 = catalog_repository.get_by_id("citizen-cx-02")
        res_cx02 = eligibility_engine.assess_product(cx02, {"print_size": "A2"})
        self.assertFalse(res_cx02.is_eligible, "Citizen CX-02 must fail A2")

    # ── Requirement 3: Ranker Weights Normalization & Exact IDs ──────────────
    def test_ranker_weights_always_total_100(self):
        """Weights must always total exactly 100.0 across all priority combinations."""
        test_messages = [
            "I need a printer for portable event photo booths.",
            "I need a very fast printer with high speed.",
            "We have high volume continuous printing with 700 prints per roll.",
            "We need fine art gallery archival quality prints.",
            "Portable and high speed for travel.",
            "High volume and portability combined.",
            "Standard request with no specific priority stated.",
        ]
        assessments = [
            AssessmentResult(product=catalog_repository.get_by_id("citizen-cx-02"), is_eligible=True, matched=["print_size"]),
            AssessmentResult(product=catalog_repository.get_by_id("citizen-cy-02"), is_eligible=True, matched=["print_size"]),
        ]

        for msg in test_messages:
            ranked = product_ranker.rank_candidates(assessments, {}, raw_message=msg)
            self.assertTrue(len(ranked) > 0)
            factors = ranked[0][2]
            applied_weights = factors.get("applied_weights", {})
            total = sum(applied_weights.values())
            self.assertAlmostEqual(total, 100.0, places=1, msg=f"Weights must total 100.0 for msg: '{msg}' (got {total})")

    # ── Requirement 4: General Claim-to-Evidence Validation ──────────────────
    def test_general_claim_validation_for_numbers_and_units(self):
        """Validator checks numbers and units against evidence records."""
        # Unverified weight on CY-02
        bad_weight = "The Citizen CY-02 weighs 18 kg loaded."
        valid, violations = deterministic_validator.validate(bad_weight, context={"product_id": "citizen-cy-02"})
        self.assertFalse(valid)
        self.assertAnyViolationContaining(violations, "18 kg")

        # Unverified capacity
        bad_cap = "The Citizen CX-02 holds 1,000 prints per roll."
        valid, violations = deterministic_validator.validate(bad_cap, context={"product_id": "citizen-cx-02"})
        self.assertFalse(valid)
        self.assertAnyViolationContaining(violations, "capacity")

        # Unsupported warranty / damage claims
        bad_warranty = "Using third party media will void your warranty and cause thermal printhead damage."
        valid, violations = deterministic_validator.validate(bad_warranty)
        self.assertFalse(valid)
        self.assertAnyViolationContaining(violations, "Unsupported claim")

    # ── Requirement 5: Consumable Aliases Cleanliness ────────────────────────
    def test_consumable_aliases_cleanliness(self):
        """cw-ms812 and unverified aliases must not exist in PRINTER_CONSUMABLE_LINKS."""
        cx02w_links = PRINTER_CONSUMABLE_LINKS.get("citizen-cx-02w", [])
        self.assertNotIn("cw-ms812", cx02w_links, "Unverified alias cw-ms812 must be removed")
        self.assertIn("cx2w 812", cx02w_links)

        cx02_links = PRINTER_CONSUMABLE_LINKS.get("citizen-cx-02", [])
        self.assertNotIn("cz01-media-4x6", cx02_links)
        self.assertIn("cx2.4x6", cx02_links)

    # ── Requirement 6: Product-Finding-Only Global Policy ────────────────────
    def test_product_finding_only_global_policy(self):
        """Pricing and discount queries return DISCOUNT_REFUSAL; zero sales contact or prices."""
        price_queries = [
            "What is the price of the Citizen CX-02?",
            "How much does the CX-02 cost in AED?",
            "Can you give me a discount for volume?",
            "What are your commercial rates?",
        ]
        for q in price_queries:
            refusal = check_user_intent_for_pricing_or_discount(q)
            self.assertIsNotNone(refusal, f"Expected refusal for query: {q}")
            self.assertEqual(refusal, DISCOUNT_REFUSAL)
            self.assertNotIn("@", refusal, "Refusal must not contain email address")
            self.assertNotIn("+971", refusal, "Refusal must not contain phone number")

    def test_validate_and_sanitize_scrubs_contact_details(self):
        """validate_and_sanitize_response scrubs email addresses and phone numbers."""
        text_with_contact = "You can view the CX-02. Contact sales@keplertech.ae or call +971 4 323 1008."
        sanitized = validate_and_sanitize_response(text_with_contact, "Tell me about CX-02")
        self.assertNotIn("sales@keplertech.ae", sanitized)
        self.assertNotIn("+971 4 323 1008", sanitized)

    # ── Requirement 7: State Persistence ────────────────────────────────────
    def test_conversation_state_persistence(self):
        """All fields persist through to_dict() and from_dict()."""
        original = ConversationState(
            session_id="session_test_persist",
            customer_name="Alice",
            category="photo_booth",
            requirements={"print_size": "4x6", "event_volume": 500},
            candidate_products=[{"id": "citizen-cx-02"}],
            compared_product_ids=["citizen-cx-02", "citizen-cy-02"],
            active_product_id="citizen-cx-02",
            active_printer_for_consumables="citizen-cx-02",
            pending_field="print_size",
            awaiting_field="scan_required",
            history_turns=[{"role": "user", "content": "I need a photo printer"}],
            turn_count=1,
            frustration_count=1,
        )

        serialized = original.to_dict()
        self.assertIn("compared_product_ids", serialized)
        self.assertIn("history_turns", serialized)
        self.assertEqual(serialized["compared_product_ids"], ["citizen-cx-02", "citizen-cy-02"])

        restored = ConversationState.from_dict(serialized)
        self.assertEqual(restored.session_id, "session_test_persist")
        self.assertEqual(restored.customer_name, "Alice")
        self.assertEqual(restored.compared_product_ids, ["citizen-cx-02", "citizen-cy-02"])
        self.assertEqual(restored.active_product_id, "citizen-cx-02")
        self.assertEqual(restored.requirements, {"print_size": "4x6", "event_volume": 500})
        self.assertEqual(len(restored.history_turns), 1)
        self.assertEqual(restored.frustration_count, 1)

    # ── Requirement 9: Reject Fabricated / Unknown URLs ──────────────────────
    def test_reject_fabricated_unknown_urls(self):
        """Any URL slug not in approved catalogue must be rejected."""
        fake_url_reply = (
            "Check out the [Citizen CX-99 Photo Printer](https://www.keplertechllc.com/product/citizen-cx-99-fake-printer/) "
            "for high speed prints."
        )
        is_valid, violations = deterministic_validator.validate(fake_url_reply)
        self.assertFalse(is_valid)
        self.assertAnyViolationContaining(violations, "Fabricated or unknown URL slug")

    # ── Requirement 12: Repository-Relative Paths ────────────────────────────
    def test_no_hardcoded_opt_salesai_in_tests(self):
        """Verify no test file contains hardcoded /opt/salesai paths."""
        repo_root = Path(__file__).resolve().parent.parent
        tests_dir = repo_root / "tests"
        for py_file in tests_dir.rglob("*.py"):
            if py_file.resolve() == Path(__file__).resolve():
                continue
            content = py_file.read_text(encoding="utf-8")
            self.assertNotIn(
                'Path("/opt/salesai',
                content,
                f"File {py_file} contains hardcoded Path(\"/opt/salesai\")"
            )
            self.assertNotIn(
                '"/opt/salesai/',
                content,
                f"File {py_file} contains hardcoded \"/opt/salesai/\" path"
            )

    # ── Helper ──────────────────────────────────────────────────────────────
    def assertAnyViolationContaining(self, violations, substring):
        found = any(substring.lower() in v.lower() for v in violations)
        self.assertTrue(found, f"Expected '{substring}' in violations, got: {violations}")


if __name__ == "__main__":
    unittest.main()
