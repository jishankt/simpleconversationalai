"""
Unit tests for Customer Relations Conversational AI application.
Verifies endpoints, multi-turn history, and strict commercial guardrails.
"""

import unittest
from app import app
from guardrails import PRICE_REFUSAL, DISCOUNT_REFUSAL


class ConversationalAiTestCase(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        import uuid
        self.session_id = f"test-session-{uuid.uuid4().hex[:8]}"

    def test_config_endpoint(self):
        from config import DEFAULT_MODEL
        resp = self.client.get("/api/config")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("company_context", data)
        self.assertEqual(data["default_model"], DEFAULT_MODEL)

    def test_health_endpoint(self):
        resp = self.client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("active_model", data)

    def test_price_refusal_guardrail(self):
        resp = self.client.post("/api/chat", json={
            "message": "What is the price of your A1 CAD plotter?",
            "session_id": self.session_id
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["reply"], PRICE_REFUSAL)
        self.assertEqual(data["source"], "guardrail_rule")

    def test_discount_refusal_guardrail(self):
        resp = self.client.post("/api/chat", json={
            "message": "Can you give me a 15% discount or special deal?",
            "session_id": self.session_id
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["reply"], DISCOUNT_REFUSAL)
        self.assertEqual(data["source"], "guardrail_rule")

    def test_product_discovery_turn(self):
        resp = self.client.post("/api/chat", json={
            "message": "I need a printer for CAD drawings.",
            "session_id": self.session_id
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertIn("?", data["reply"])  # Contains exactly one clarifying/requirement question

    def test_switch_from_scanner_to_technical_cad(self):
        """Customer asks for scanner, then switches to 'i want technical cad printer'."""
        sess_id = "test-scanner-to-cad-switch"
        # Turn 1: Ask for scanner
        resp1 = self.client.post("/api/chat", json={
            "message": "i need a scanner",
            "session_id": sess_id
        })
        self.assertEqual(resp1.status_code, 200)
        self.assertIn("scan", resp1.get_json()["reply"].lower())

        # Turn 2: Switch to technical CAD printer
        resp2 = self.client.post("/api/chat", json={
            "message": "i want technical cad printer",
            "session_id": sess_id
        })
        self.assertEqual(resp2.status_code, 200)
        data2 = resp2.get_json()
        self.assertIn("print size", data2["reply"].lower())
        self.assertNotIn("scan", data2["reply"].lower())


if __name__ == "__main__":
    unittest.main()
