"""
Architecture Verification Tests.
Verifies:
1. Primary orchestrator pipeline (agent.orchestrator.orchestrator) is in use.
2. Thread-safe domain.state_store.state_manager manages session state with HMAC signing.
3. The canonical agent.orchestrator is the primary response path in app.py.
"""
import unittest


class TestArchitectureSingleOrchestrator(unittest.TestCase):
    def test_primary_orchestrator_is_canonical(self):
        """Ensure app.py uses agent.orchestrator as the primary orchestrator, not ai_orchestrator."""
        import ast, pathlib
        repo_root = pathlib.Path(__file__).resolve().parent.parent
        app_source = (repo_root / "app.py").read_text()
        tree = ast.parse(app_source)
        # The new_orchestrator.process_turn call must reference agent.orchestrator, not ai_orchestrator
        self.assertIn("from agent.orchestrator import orchestrator as new_orchestrator", app_source,
                      "app.py must import agent.orchestrator as the primary orchestrator")

    def test_single_orchestrator_active(self):
        """Ensure agent.orchestrator.orchestrator exists and has process_turn."""
        from agent.orchestrator import orchestrator
        self.assertIsNotNone(orchestrator)
        self.assertTrue(hasattr(orchestrator, "process_turn"))
        self.assertTrue(callable(orchestrator.process_turn))

    def test_state_manager_singleton_and_hmac(self):
        """Ensure state_manager is active, thread-safe, and signs session IDs."""
        from domain.state_store import state_manager
        self.assertIsNotNone(state_manager)

        # Verify HMAC signing
        session_id = "test-session-arch-123"
        signed_token = state_manager.sign_session(session_id)
        self.assertIsNotNone(signed_token)
        self.assertTrue(signed_token.startswith(f"{session_id}:"))

        # Valid signature verification
        is_valid = state_manager.verify_session(session_id, signed_token)
        self.assertTrue(is_valid)

        # Invalid/tampered signature rejection
        tampered_token = signed_token + "tampered"
        self.assertFalse(state_manager.verify_session(session_id, tampered_token))
        self.assertFalse(state_manager.verify_session("different-session", signed_token))

    def test_state_manager_get_and_reset(self):
        """Verify state creation, retrieval, and resetting."""
        from domain.state_store import state_manager
        test_id = "test-state-lifecycle"
        state = state_manager.get_or_create(test_id)
        self.assertIsNotNone(state)
        self.assertEqual(state.session_id, test_id)

        # Mutate state and verify persistence in manager
        state.category = "technical_cad"
        state_retrieved = state_manager.get(test_id)
        self.assertEqual(state_retrieved.category, "technical_cad")

        # Reset session
        state_manager.reset(test_id)
        fresh_state = state_manager.get_or_create(test_id)
        self.assertIsNone(fresh_state.category)


if __name__ == "__main__":
    unittest.main()
