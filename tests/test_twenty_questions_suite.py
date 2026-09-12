"""
20 Targeted Regression Question Test Suite for Kepler Tech SalesAI.
Validates the exact 20 customer questions and expected card counts/models.
"""
import unittest
from domain.conversation_state import ConversationState
from agent.orchestrator import orchestrator


class TestTwentyQuestionsSuite(unittest.TestCase):

    def test_01_a4_office_printer(self):
        """Test 1 — A4 office printer -> 4 cards."""
        q = "I need an A4 colour multifunction printer for my office. It must print, scan and copy, and we print approximately 200 pages per day. Show me all matching catalogue models."
        state = ConversationState(session_id="test-20-q1")
        res = orchestrator.process_turn(q, state=state)
        cards = res.get("cards", [])
        self.assertEqual(len(cards), 4)
        card_ids = set(c["id"] for c in cards)
        self.assertEqual(card_ids, {"epson-wf-c5890-dwf", "epson-em-c800", "epson-am-c400", "epson-am-c550"})

    def test_02_a3_workforce_pro_printer(self):
        """Test 2 — A3 WorkForce Pro printer -> 2 cards."""
        q = "I need an A3 colour multifunction printer for a busy office. It must print, scan and copy, and our daily volume is approximately 150 pages. Show every suitable WorkForce Pro model from the catalogue."
        state = ConversationState(session_id="test-20-q2")
        res = orchestrator.process_turn(q, state=state)
        cards = res.get("cards", [])
        self.assertEqual(len(cards), 2)
        card_ids = set(c["id"] for c in cards)
        self.assertEqual(card_ids, {"epson-wf-c878r-dwf", "epson-wf-c879r-dwf"})

    def test_03_a3_enterprise_printer(self):
        """Test 3 — A3 enterprise printer -> 4 cards."""
        q = "We need an A3 colour multifunction printer for an enterprise office. It must support printing, scanning and copying, and we expect approximately 800 pages per day. Show all enterprise models in the approved catalogue."
        state = ConversationState(session_id="test-20-q3")
        res = orchestrator.process_turn(q, state=state)
        cards = res.get("cards", [])
        self.assertEqual(len(cards), 4)
        card_ids = set(c["id"] for c in cards)
        self.assertEqual(card_ids, {"epson-am-c4000", "epson-am-c5000", "epson-am-c6000", "epson-wf-c21000-d4tw"})

    def test_04_24_inch_cad_printer(self):
        """Test 4 — 24-inch CAD printer -> 4 cards."""
        q = "I need a 24-inch printer for CAD drawings and architectural plans. I do not need an integrated scanner, and we print approximately 30 drawings per day. Show all matching technical printers."
        state = ConversationState(session_id="test-20-q4")
        res = orchestrator.process_turn(q, state=state)
        cards = res.get("cards", [])
        self.assertEqual(len(cards), 4)
        card_ids = set(c["id"] for c in cards)
        self.assertEqual(card_ids, {"epson-sc-t3100", "epson-sc-t3700e", "epson-sc-t3700d", "epson-sc-t3700de"})

    def test_05_36_inch_cad_printer_without_scanning(self):
        """Test 5 — 36-inch CAD printer without scanning -> 3 cards."""
        q = "I need a 36-inch printer for CAD drawings, construction plans and technical documents. I do not need scanning, and we print around 50 drawings daily. List every matching catalogue printer."
        state = ConversationState(session_id="test-20-q5")
        res = orchestrator.process_turn(q, state=state)
        cards = res.get("cards", [])
        self.assertEqual(len(cards), 3)
        card_ids = set(c["id"] for c in cards)
        self.assertEqual(card_ids, {"epson-sc-t5100", "epson-sc-t5405", "epson-sc-t5700d"})

    def test_06_36_inch_cad_multifunction_printer(self):
        """Test 6 — 36-inch CAD multifunction printer -> 3 cards."""
        q = "I need a 36-inch CAD plotter for architectural drawings. It must have an integrated scanner for printing, scanning and copying, and our expected volume is approximately 40 drawings per day. Show all matching models."
        state = ConversationState(session_id="test-20-q6")
        res = orchestrator.process_turn(q, state=state)
        cards = res.get("cards", [])
        self.assertEqual(len(cards), 3)
        card_ids = set(c["id"] for c in cards)
        self.assertEqual(card_ids, {"epson-sc-t5100m", "epson-sc-t5400m", "epson-sc-t5700dm"})

    def test_07_44_inch_cad_printer_without_scanning(self):
        """Test 7 — 44-inch CAD printer without scanning -> 2 cards."""
        q = "I need a 44-inch technical printer for engineering drawings and large CAD plans. I do not need a scanner, and we print approximately 70 drawings daily. Show every matching catalogue model."
        state = ConversationState(session_id="test-20-q7")
        res = orchestrator.process_turn(q, state=state)
        cards = res.get("cards", [])
        self.assertEqual(len(cards), 2)
        card_ids = set(c["id"] for c in cards)
        self.assertEqual(card_ids, {"epson-sc-t7700d", "epson-sc-t7700dl"})

    def test_08_44_inch_cad_multifunction_printer(self):
        """Test 8 — 44-inch CAD multifunction printer -> 1 card."""
        q = "I need a 44-inch multifunction technical printer for CAD drawings. It must support printing, scanning and copying, and we process around 60 drawings every day. Show all matching catalogue products."
        state = ConversationState(session_id="test-20-q8")
        res = orchestrator.process_turn(q, state=state)
        cards = res.get("cards", [])
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["id"], "epson-sc-t7700dm")

    def test_09_a3_plus_professional_photography(self):
        """Test 9 — A3+ professional photography -> 1 card."""
        q = "I am a professional photographer and need a desktop printer for gallery-quality photos up to A3+. I expect approximately 20 prints per day. Show all matching catalogue printers."
        state = ConversationState(session_id="test-20-q9")
        res = orchestrator.process_turn(q, state=state)
        cards = res.get("cards", [])
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["id"], "epson-sc-p700")

    def test_10_a2_plus_professional_photography(self):
        """Test 10 — A2+ professional photography -> 2 base-model cards, SC-P900 grouped."""
        q = "I need a professional desktop photo printer for fine-art and portrait printing up to A2+. I print approximately 25 photographs daily. Show all matching catalogue products, including available configurations."
        state = ConversationState(session_id="test-20-q10")
        res = orchestrator.process_turn(q, state=state)
        cards = res.get("cards", [])
        self.assertEqual(len(cards), 2)
        card_ids = set(c["id"] for c in cards)
        self.assertEqual(card_ids, {"epson-sc-p900", "epson-sc-p5300"})
        p900_card = next(c for c in cards if c["id"] == "epson-sc-p900")
        self.assertEqual(p900_card.get("available_configurations"), ["Standard", "Roll Adapter"])

    def test_11_24_inch_professional_photography(self):
        """Test 11 — 24-inch professional photography -> 4 base-model cards."""
        q = "I need a 24-inch professional printer for photography, fine art and high-quality posters. We produce approximately 40 prints daily. Scanning is not required. Show every matching catalogue model."
        state = ConversationState(session_id="test-20-q11")
        res = orchestrator.process_turn(q, state=state)
        cards = res.get("cards", [])
        self.assertEqual(len(cards), 4)
        card_ids = set(c["id"] for c in cards)
        self.assertEqual(card_ids, {"epson-sc-p6500e", "epson-sc-p6500d", "epson-sc-p6500de", "epson-sc-p7500"})
        p7500_card = next(c for c in cards if c["id"] == "epson-sc-p7500")
        self.assertEqual(p7500_card.get("available_configurations"), ["Standard", "Spectro"])

    def test_12_24_inch_dual_roll_photography_printer(self):
        """Test 12 — 24-inch dual-roll photography printer -> 2 cards."""
        q = "I need a 24-inch professional photo and poster printer with dual-roll support. I do not need scanning, and we produce around 50 prints daily. Show every matching catalogue product."
        state = ConversationState(session_id="test-20-q12")
        res = orchestrator.process_turn(q, state=state)
        cards = res.get("cards", [])
        self.assertEqual(len(cards), 2)
        card_ids = set(c["id"] for c in cards)
        self.assertEqual(card_ids, {"epson-sc-p6500d", "epson-sc-p6500de"})

    def test_13_44_inch_professional_photography(self):
        """Test 13 — 44-inch professional photography -> 2 base-model cards."""
        q = "I need a 44-inch professional printer for commercial photography, fine-art reproduction and posters. Scanning is not required, and our expected production is approximately 60 prints per day. Show every matching catalogue printer."
        state = ConversationState(session_id="test-20-q13")
        res = orchestrator.process_turn(q, state=state)
        cards = res.get("cards", [])
        self.assertEqual(len(cards), 2)
        card_ids = set(c["id"] for c in cards)
        self.assertEqual(card_ids, {"epson-sc-p8500d", "epson-sc-p9500"})
        p9500_card = next(c for c in cards if c["id"] == "epson-sc-p9500")
        self.assertEqual(p9500_card.get("available_configurations"), ["Standard", "Spectro"])

    def test_14_44_inch_photo_printer_with_scanning(self):
        """Test 14 — 44-inch photo printer with scanning -> 1 card."""
        q = "I need a 44-inch professional printer for photos and posters. It must include multifunction scanning, and we process approximately 40 prints per day. Show all matching catalogue models."
        state = ConversationState(session_id="test-20-q14")
        res = orchestrator.process_turn(q, state=state)
        cards = res.get("cards", [])
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["id"], "epson-sc-p8500dm")

    def test_15_64_inch_production_photo_printer(self):
        """Test 15 — 64-inch production photo printer -> 1 card."""
        q = "I need a 64-inch production printer for professional photography, fine art, posters and indoor signage. We expect approximately 100 prints daily. Show all matching catalogue products."
        state = ConversationState(session_id="test-20-q15")
        res = orchestrator.process_turn(q, state=state)
        cards = res.get("cards", [])
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["id"], "epson-sc-p20500")

    def test_16_compact_4x4_citizen_printer(self):
        """Test 16 — Compact 4x4 Citizen printer -> 1 card."""
        q = "I need a compact and portable direct photo printer for mobile events. I must print 4×4 and 4×6 photos, and I expect approximately 150 prints per event. Show every matching Citizen printer."
        state = ConversationState(session_id="test-20-q16")
        res = orchestrator.process_turn(q, state=state)
        cards = res.get("cards", [])
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["id"], "citizen-cz-01")

    def test_17_citizen_4x6_and_6x8_printing(self):
        """Test 17 — Citizen 4x6 and 6x8 printing -> 2 cards."""
        q = "I need a direct dye-sublimation printer for a photo studio. It must print both 4×6 and 6×8 photos, and we expect approximately 400 prints per day. Portability is not mandatory. Show every matching Citizen model."
        state = ConversationState(session_id="test-20-q17")
        res = orchestrator.process_turn(q, state=state)
        cards = res.get("cards", [])
        self.assertEqual(len(cards), 2)
        card_ids = set(c["id"] for c in cards)
        self.assertEqual(card_ids, {"citizen-cx-02", "citizen-cy-02"})

    def test_18_high_capacity_citizen_printer(self):
        """Test 18 — High-capacity Citizen printer -> 1 card (CY-02)."""
        q = "I need a direct dye-sublimation photo printer for a busy fixed kiosk. It must print 4×6 and 6×8 photos, and we expect more than 700 prints per day. High media capacity is more important than portability. Show all matching models."
        state = ConversationState(session_id="test-20-q18")
        res = orchestrator.process_turn(q, state=state)
        cards = res.get("cards", [])
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["id"], "citizen-cy-02")

    def test_19_8x10_and_8x12_citizen_printer(self):
        """Test 19 — 8x10 and 8x12 Citizen printer -> 1 card (CX-02W)."""
        q = "I need a direct dye-sublimation printer for my studio. It must print both 8×10 and 8×12 photographs, and we expect approximately 100 prints daily. Show every matching Citizen model."
        state = ConversationState(session_id="test-20-q19")
        res = orchestrator.process_turn(q, state=state)
        cards = res.get("cards", [])
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["id"], "citizen-cx-02w")

    def test_20_full_natural_language_requirement(self):
        """Test 20 — Full natural-language requirement -> 3 cards."""
        q = "We are an architectural company producing around 1,200 technical drawings every month. Most drawings are A0, so we need 36-inch output. We also need to scan old drawings and make copies. Please show every suitable printer from your approved catalogue."
        state = ConversationState(session_id="test-20-q20")
        res = orchestrator.process_turn(q, state=state)
        cards = res.get("cards", [])
        self.assertEqual(len(cards), 3)
        card_ids = set(c["id"] for c in cards)
        self.assertEqual(card_ids, {"epson-sc-t5100m", "epson-sc-t5400m", "epson-sc-t5700dm"})
        self.assertEqual(state.requirements.get("monthly_volume"), 1200)
        self.assertEqual(state.requirements.get("daily_volume"), 40)
        self.assertEqual(state.requirements.get("print_width"), 36)
        self.assertTrue(state.requirements.get("scanner_required"))


if __name__ == "__main__":
    unittest.main()
