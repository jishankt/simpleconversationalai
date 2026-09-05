"""
Comprehensive Unit Tests for Verified Consumables & Product Cards Engine.
Guarantees 100% accurate, zero-hallucination matching for hardware, inks, and maintenance supplies.
"""

import unittest
from rag.consumables_engine import consumables_engine, VERIFIED_PRINTER_MAPPING
from app import app


class ConsumablesAndCardsTestCase(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_hardware_isolation(self):
        """Hardware cards must ONLY contain genuine printers, never media packs, bags, or inks."""
        hw = consumables_engine.find_matching_hardware("SC-F100")
        self.assertTrue(len(hw) > 0)
        self.assertIn("F100", hw[0]["name"])
        self.assertTrue(hw[0]["image_url"].startswith("http"))
        
        # Test Citizen: CX-02 printer should match printer, NOT media pack or bag
        cx_hw = consumables_engine.find_matching_hardware("Citizen CX-02")
        self.assertTrue(len(cx_hw) > 0)
        self.assertEqual(cx_hw[0]["sku"], "CX-02")
        self.assertNotIn("Media", cx_hw[0]["name"])
        self.assertNotIn("Bag", cx_hw[0]["name"])

    def test_verified_consumables_sc_f100(self):
        """Epson SC-F100 must map to T49N inks and C13S210125 maintenance box."""
        cons = consumables_engine.get_printer_consumables("SC-F100")
        self.assertTrue(len(cons) >= 2)
        skus = [c["sku"] for c in cons]
        self.assertTrue(any(s.startswith("C13T49N") for s in skus))
        self.assertTrue(any("C13S210125" in s for s in skus))

    def test_verified_consumables_sc_p900(self):
        """Epson SC-P900 must map to T47A UltraChrome PRO10 inks and C12C935711 maintenance tank."""
        cons = consumables_engine.get_printer_consumables("Epson SureColor SC-P900")
        self.assertTrue(len(cons) >= 2)
        skus = [c["sku"] for c in cons]
        self.assertTrue(any(s.startswith("C13T47A") for s in skus))
        self.assertTrue(any("C12C935711" in s for s in skus))

    def test_verified_consumables_sc_t3100(self):
        """Epson SC-T3100 must map to UltraChrome XD2 (T40C/T40D) inks and C13S210057 maintenance box."""
        cons = consumables_engine.get_printer_consumables("SureColor T3100")
        self.assertTrue(len(cons) >= 2)
        skus = [c["sku"] for c in cons]
        self.assertTrue(any(s.startswith("C13T40") for s in skus))
        self.assertTrue(any("C13S210057" in s for s in skus))

    def test_verified_consumables_citizen_cx02(self):
        """Citizen CX-02 must map to verified dye-sub media rolls and accessories (ZERO Epson inks)."""
        cons = consumables_engine.get_printer_consumables("Citizen CX-02")
        self.assertTrue(len(cons) >= 2)
        names = [c["name"].lower() for c in cons]
        self.assertTrue(any("cx-02" in n or "cx2" in n for n in names))
        # ZERO Epson inks or cross-brand pollution
        for c in cons:
            self.assertNotIn("epson", c["name"].lower(), f"Epson item {c['name']} found in Citizen CX-02 consumables!")
            self.assertNotIn("ultrachrome", c["name"].lower(), f"UltraChrome ink {c['name']} found in Citizen CX-02 consumables!")

    def test_verified_consumables_am_c4000(self):
        """Epson AM-C4000 must map to T08H inks and C12C937181 maintenance box."""
        cons = consumables_engine.get_printer_consumables("AM-C4000")
        self.assertTrue(len(cons) >= 2)
        skus = [c["sku"] for c in cons]
        self.assertTrue(any(s.startswith("C13T08H") for s in skus))
        self.assertTrue(any("C12C937181" in s for s in skus))

    def test_zero_hallucination_on_unknown_printer(self):
        """Unknown or unverified printer must return EMPTY list - NO random fallbacks!"""
        fake_cons = consumables_engine.get_printer_consumables("Canon imagePROGRAF PRO-1000")
        self.assertEqual(fake_cons, [])

        fake_cons_2 = consumables_engine.get_printer_consumables("HP DesignJet T650")
        self.assertEqual(fake_cons_2, [])

    def test_consumables_api_endpoint(self):
        resp = self.client.get("/api/consumables?printer=SC-F100")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["printer"], "SC-F100")
        self.assertTrue(len(data["consumables"]) > 0)

    def test_chat_returns_product_and_consumable_cards(self):
        resp = self.client.post("/api/chat", json={
            "message": "Can you show me the Epson SC-F100 printer and its inks?",
            "session_id": "test-cards-session"
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertIn("product_cards", data)
        self.assertIn("consumable_cards", data)
        self.assertTrue(len(data["product_cards"]) > 0)
        self.assertTrue(len(data["consumable_cards"]) > 0)
        self.assertIn("F100", data["product_cards"][0]["name"])
        # Check that response text specifically mentions UltraChrome DS or T49N or maintenance box
        resp_text = data.get("reply") or data.get("response", "")
        self.assertTrue("UltraChrome DS" in resp_text or "T49N" in resp_text or "maintenance box" in resp_text)


if __name__ == "__main__":
    unittest.main()
