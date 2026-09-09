"""
Architecture tests: verify security config, SSRF/model allowlist guards,
security headers, and single-orchestrator design.

NOTE: ai_orchestrator.py exists in this branch as a legacy fallback module.
The test confirms it is NOT the primary routing path — agent/orchestrator.py is.
"""

import unittest
import importlib
import os


class TestSecurityConfig(unittest.TestCase):
    """Verify that all required security fields are present in config."""

    def test_secret_key_exists(self):
        import config
        self.assertTrue(hasattr(config, "SECRET_KEY"), "config.SECRET_KEY missing")
        self.assertIsInstance(config.SECRET_KEY, str)
        self.assertGreater(len(config.SECRET_KEY), 0)

    def test_allowed_models_exists(self):
        import config
        self.assertTrue(hasattr(config, "ALLOWED_MODELS"), "config.ALLOWED_MODELS missing")
        self.assertIsInstance(config.ALLOWED_MODELS, list)
        self.assertGreater(len(config.ALLOWED_MODELS), 0)

    def test_cors_origins_exists(self):
        import config
        self.assertTrue(hasattr(config, "CORS_ORIGINS"), "config.CORS_ORIGINS missing")
        self.assertIsInstance(config.CORS_ORIGINS, list)

    def test_max_request_bytes_exists(self):
        import config
        self.assertTrue(hasattr(config, "MAX_REQUEST_BYTES"), "config.MAX_REQUEST_BYTES missing")
        self.assertIsInstance(config.MAX_REQUEST_BYTES, int)
        self.assertGreater(config.MAX_REQUEST_BYTES, 0)

    def test_default_model_in_allowed_models(self):
        import config
        self.assertIn(
            config.DEFAULT_MODEL, config.ALLOWED_MODELS,
            f"DEFAULT_MODEL '{config.DEFAULT_MODEL}' must be in ALLOWED_MODELS"
        )


class TestSecurityHeaders(unittest.TestCase):
    """Verify that security headers are attached to every response."""

    def setUp(self):
        from app import app
        self.client = app.test_client()

    def test_security_headers_on_health(self):
        resp = self.client.get("/api/health")
        self.assertEqual(resp.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(resp.headers.get("X-Frame-Options"), "DENY")
        self.assertIn("X-XSS-Protection", resp.headers)
        self.assertIn("Referrer-Policy", resp.headers)

    def test_security_headers_on_chat(self):
        resp = self.client.post("/api/chat", json={"message": "hello"})
        self.assertEqual(resp.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(resp.headers.get("X-Frame-Options"), "DENY")


class TestSSRFAndModelAllowlist(unittest.TestCase):
    """Verify SSRF and model-injection guards in /api/chat."""

    def setUp(self):
        from app import app
        import uuid
        self.client = app.test_client()
        self.session_id = f"test-security-{uuid.uuid4().hex[:8]}"

    def test_disallowed_model_falls_back_to_default(self):
        """Sending a disallowed model name must not crash; it should fall back silently."""
        resp = self.client.post("/api/chat", json={
            "message": "hello",
            "session_id": self.session_id,
            "model": "evil-model:latest"  # not in ALLOWED_MODELS
        })
        # Should still return 200 (fell back to DEFAULT_MODEL)
        self.assertEqual(resp.status_code, 200)

    def test_oversized_request_rejected(self):
        """A request body exceeding MAX_REQUEST_BYTES must return 413."""
        from config import MAX_REQUEST_BYTES
        big_message = "A" * (MAX_REQUEST_BYTES + 1)
        resp = self.client.post(
            "/api/chat",
            data=big_message,
            content_type="application/json",
            content_length=len(big_message)
        )
        self.assertEqual(resp.status_code, 413)


class TestSingleOrchestratorArchitecture(unittest.TestCase):
    """
    Verify that agent/orchestrator.py is the primary routing path.

    NOTE: ai_orchestrator.py exists as a legacy fallback module in this branch.
    We do NOT assert it is removed — we assert it is NOT wired as the primary path.
    """

    def test_primary_orchestrator_importable(self):
        """agent.orchestrator must be importable and expose a process_turn method."""
        from agent.orchestrator import orchestrator
        self.assertTrue(
            hasattr(orchestrator, "process_turn"),
            "agent.orchestrator must have a process_turn method"
        )

    def test_legacy_orchestrator_is_fallback_only(self):
        """
        ai_orchestrator exists as a fallback import in app.py.
        It must NOT be the object wired to new_orchestrator in app.py.
        """
        from agent.orchestrator import orchestrator as new_orchestrator
        try:
            from agent.ai_orchestrator import ai_orchestrator
            # If both exist, confirm the app uses the new one as primary
            self.assertIsNot(
                new_orchestrator, ai_orchestrator,
                "app.py must use agent.orchestrator as primary, not ai_orchestrator"
            )
        except ImportError:
            # ai_orchestrator removed entirely — even better
            pass

    def test_app_uses_new_orchestrator(self):
        """app.py must import and wire agent.orchestrator, not ai_orchestrator, as new_orchestrator."""
        import app as app_module
        from agent.orchestrator import orchestrator as expected
        # The module-level new_orchestrator variable must point to the canonical orchestrator
        self.assertIs(app_module.new_orchestrator, expected)

    def test_decision_engine_importable(self):
        """agent.decision_engine must be importable (routing lives here)."""
        from agent import decision_engine
        self.assertTrue(hasattr(decision_engine, "decide"), "decision_engine must expose a decide() function")


if __name__ == "__main__":
    unittest.main(verbosity=2)
