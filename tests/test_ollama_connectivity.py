"""
Unit and Integration Tests for Ollama Connectivity, Health Checks,
Error Logging, and Grounded Routing Priorities.
"""

import unittest
from unittest.mock import patch, MagicMock
import requests
import json

from ollama_client import OllamaClient, OllamaErrorKind, classify_request_error
from domain.conversation_types import Intent, RouteName, LLMUnderstanding
from domain.conversation_state import ConversationState
from nlp.llm_understanding import LLMUnderstandingEngine
from agent.decision_engine import decide
from routes import comparison_route, product_route


class TestOllamaDiagnostics(unittest.TestCase):
    """Tests health check, error categorization, timeouts, and JSON parse handling."""

    def test_online_health_check(self):
        client = OllamaClient(base_url="http://mock-ollama:11434", default_model="qwen2.5:32b")

        def mock_requests(url, *args, **kwargs):
            mock_resp = MagicMock()
            if "/api/tags" in url:
                mock_resp.status_code = 200
                mock_resp.json.return_value = {"models": [{"name": "qwen2.5:32b"}]}
                return mock_resp
            elif "/api/chat" in url:
                mock_resp.status_code = 200
                mock_resp.json.return_value = {"message": {"content": "pong"}}
                return mock_resp
            mock_resp.status_code = 404
            return mock_resp

        with patch("requests.get", side_effect=mock_requests), \
             patch("requests.post", side_effect=mock_requests):
            health = client.startup_health_check()
            self.assertTrue(health["online"])
            self.assertTrue(health["connectivity"])
            self.assertTrue(health["model_available"])
            self.assertTrue(health["inference_working"])
            self.assertIsNone(health["error_kind"])

    def test_offline_connection_refused_server_unavailable(self):
        client = OllamaClient(base_url="http://192.168.0.110:11434", default_model="qwen2.5:32b")
        conn_err = requests.exceptions.ConnectionError(
            "HTTPConnectionPool(host='192.168.0.110', port=11434): "
            "Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it"
        )
        with patch("requests.get", side_effect=conn_err):
            health = client.startup_health_check()
            self.assertFalse(health["online"])
            self.assertFalse(health["connectivity"])
            self.assertEqual(health["error_kind"], OllamaErrorKind.SERVER_UNAVAILABLE.value)

    def test_connection_timeout(self):
        client = OllamaClient(base_url="http://192.168.0.110:11434", default_model="qwen2.5:32b")
        timeout_err = requests.exceptions.ConnectTimeout("Connection to 192.168.0.110 timed out. (connect timeout=2.5)")
        with patch("requests.get", side_effect=timeout_err):
            health = client.startup_health_check()
            self.assertFalse(health["online"])
            self.assertEqual(health["error_kind"], OllamaErrorKind.CONNECTION_TIMEOUT.value)

    def test_read_timeout_classification(self):
        read_timeout = requests.exceptions.ReadTimeout("Read timed out.")
        self.assertEqual(classify_request_error(read_timeout), OllamaErrorKind.READ_TIMEOUT)

    def test_model_not_installed(self):
        client = OllamaClient(base_url="http://mock-ollama:11434", default_model="qwen2.5:32b")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"models": [{"name": "llama3:8b"}, {"name": "mistral:7b"}]}
        with patch("requests.get", return_value=mock_resp):
            health = client.startup_health_check()
            self.assertFalse(health["online"])
            self.assertTrue(health["connectivity"])
            self.assertFalse(health["model_available"])
            self.assertEqual(health["error_kind"], OllamaErrorKind.MODEL_NOT_INSTALLED.value)

    def test_invalid_response_status(self):
        client = OllamaClient(base_url="http://mock-ollama:11434", default_model="qwen2.5:32b")
        mock_resp = MagicMock()
        mock_resp.status_code = 502
        mock_resp.text = "Bad Gateway"
        with patch("requests.get", return_value=mock_resp):
            health = client.startup_health_check()
            self.assertFalse(health["online"])
            self.assertEqual(health["error_kind"], OllamaErrorKind.INVALID_RESPONSE.value)

    def test_json_parse_failure_in_classify(self):
        client = OllamaClient(base_url="http://mock-ollama:11434", default_model="qwen2.5:32b")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"message": {"content": "This is raw unformatted text, not JSON."}}
        with patch("requests.post", return_value=mock_resp):
            res = client.classify(messages=[{"role": "user", "content": "hi"}], schema={})
            self.assertFalse(res["success"])
            self.assertTrue(res["fallback_used"])
            self.assertEqual(res["error_kind"], OllamaErrorKind.JSON_PARSE_FAILURE.value)


class TestRoutingPriority(unittest.TestCase):
    """Tests routing priority under offline and fallback conditions."""

    def setUp(self):
        self.nlu = LLMUnderstandingEngine(ollama_client=None)

    def test_fastest_citizen_printer_bypasses_qualification(self):
        """Verify 'Which Citizen printer is the fastest?' provides specs and bypasses qualification."""
        query = "Which Citizen printer is the fastest?"
        state = ConversationState(session_id="test_fastest")
        state.category = "photo_booth"

        # NLU classification
        und = self.nlu.understand(query, [], state.to_dict())
        self.assertIn(und.intent, [Intent.PRODUCT_COMPARISON, Intent.PRODUCT_QUESTION])
        self.assertNotEqual(und.intent, Intent.PRODUCT_DISCOVERY)

        # Decision engine
        dec = decide(und, state, raw_message=query)
        self.assertIn(dec.route, [RouteName.PRODUCT, RouteName.COMPARISON])
        self.assertNotEqual(dec.route, RouteName.QUALIFICATION)

        # Execute comparison route
        res = comparison_route.handle(und, state, raw_message=query)
        self.assertFalse(res.needs_composition)
        self.assertIn("12.4 seconds", res.reply)
        self.assertIn("CY-02", res.reply)
        self.assertIn("CX-02", res.reply)
        self.assertNotIn("What photo print sizes do you need", res.reply)

    def test_comparison_t3100_vs_t5100_bypasses_qualification(self):
        """Verify 'Compare Epson SureColor T3100 vs T5100' routes to comparison and bypasses qualification."""
        query = "Compare Epson SureColor T3100 vs T5100"
        state = ConversationState(session_id="test_comp")

        und = self.nlu.understand(query, [], state.to_dict())
        self.assertEqual(und.intent, Intent.PRODUCT_COMPARISON)

        dec = decide(und, state, raw_message=query)
        self.assertEqual(dec.route, RouteName.COMPARISON)

        res = comparison_route.handle(und, state, raw_message=query)
        self.assertIn("T3100", res.reply)
        self.assertIn("T5100", res.reply)
        self.assertIn("24 inches", res.reply)
        self.assertIn("36 inches", res.reply)
        self.assertFalse(res.needs_composition)

    def test_consultative_cad_request_routes_to_qualification(self):
        """Verify consultative discovery requests ('Recommend a printer for CAD') route to qualification."""
        query = "Recommend a printer for CAD"
        state = ConversationState(session_id="test_cad_qual")

        und = self.nlu.understand(query, [], state.to_dict())
        self.assertEqual(und.intent, Intent.PRODUCT_DISCOVERY)

        dec = decide(und, state, raw_message=query)
        self.assertEqual(dec.route, RouteName.QUALIFICATION)


if __name__ == "__main__":
    unittest.main()
