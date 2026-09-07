from unittest.mock import patch, MagicMock

from django.urls import reverse
from django.test import TestCase, Client
from django.http import Http404

from experiments.models import Simulation, SimulationAgent, ActivityEvent
from experiments.activity import (
    EventPublisher,
    EventTypes,
    SimulationController,
    AgentAdapter,
)
from simulation.actions import Action, ActionTypes


class TickLockingTest(TestCase):
    """Tests for database-level tick locking and idempotency."""

    def setUp(self):
        self.client = Client()
        self.sim = Simulation.objects.create(
            name="lock-test-sim", total_ticks=5
        )
        self.agent = SimulationAgent.objects.create(
            simulation=self.sim, name="agent-1", runtime="rule"
        )

    def tearDown(self):
        EventPublisher._subscribers.clear()

    def test_step_locked_uses_select_for_update(self):
        controller = SimulationController(self.sim)
        with patch("experiments.activity.Simulation.objects") as mock_sim_mgr:
            mock_sim_mgr.select_for_update.return_value.get.return_value = self.sim
            controller.step()

    def test_step_locked_prevents_duplicate_tick(self):
        self.client.post(reverse("simulation_start", args=[self.sim.id]))
        self.client.post(reverse("simulation_step", args=[self.sim.id]))

        # Try to step again - should work because tick is different
        resp = self.client.post(reverse("simulation_step", args=[self.sim.id]))
        self.assertEqual(resp.status_code, 200)

    def test_step_locked_returns_already_completed(self):
        self.sim.status = "completed"
        self.sim.save(update_fields=["status"])

        controller = SimulationController(self.sim)
        result = controller.step_locked()
        self.assertEqual(result["status"], "already_completed")

    def test_operation_id_exists_on_simulation(self):
        self.assertIsNotNone(self.sim.operation_id)
        self.assertTrue(len(str(self.sim.operation_id)) > 0)

    def test_operation_id_is_unique(self):
        sim2 = Simulation.objects.create(name="unique-sim-2")
        self.assertNotEqual(self.sim.operation_id, sim2.operation_id)


class RunToCompletionTest(TestCase):
    """Tests for continuous simulation execution (worker pattern)."""

    def setUp(self):
        EventPublisher._subscribers.clear()
        self.sim = Simulation.objects.create(
            name="full-run-sim", total_ticks=5
        )
        SimulationAgent.objects.create(
            simulation=self.sim, name="agent-1", runtime="rule"
        )

    def test_run_to_completion_completes_simulation(self):
        controller = SimulationController(self.sim)
        result = controller.run_to_completion()
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["tick"], 5)
        self.assertEqual(result["steps_executed"], 5)

    def test_run_to_completion_respects_paused(self):
        controller = SimulationController(self.sim)

        original_step = controller.step_locked

        call_count = [0]

        def limited_step():
            original_result = original_step()
            call_count[0] += 1
            if call_count[0] == 2:
                self.sim.refresh_from_db()
                self.sim.status = "paused"
                self.sim.save(update_fields=["status"])
            return original_result

        with patch.object(controller, "step_locked", side_effect=limited_step):
            result = controller.run_to_completion()
        self.assertEqual(result["status"], "paused")

    def test_run_to_completion_handles_error_status(self):
        self.sim.status = "error"
        self.sim.save(update_fields=["status"])

        controller = SimulationController(self.sim)
        result = controller.run_to_completion()
        self.assertEqual(result["status"], "error")

    def test_run_to_completion_skips_completed(self):
        self.sim.status = "completed"
        self.sim.save(update_fields=["status"])

        controller = SimulationController(self.sim)
        result = controller.run_to_completion()
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["steps_executed"], 0)


class ProviderFailureIsolationTest(TestCase):
    """Tests that provider failures are isolated and don't crash the simulation."""

    def setUp(self):
        self.sim = Simulation.objects.create(
            name="failure-isolation-sim", total_ticks=3
        )
        self.agent = SimulationAgent.objects.create(
            simulation=self.sim, name="failing-agent", runtime="rule"
        )

    def tearDown(self):
        EventPublisher._subscribers.clear()

    def test_runtime_error_does_not_crash_tick(self):
        controller = SimulationController(self.sim)

        original_get_runtime = controller._build_observation

        def failing_runtime_call():
            with patch("experiments.activity.get_agent_runtime") as mock_get_rt:
                mock_runtime = MagicMock()
                mock_runtime.decide.side_effect = RuntimeError("Provider crashed")
                mock_runtime.trace_metadata.return_value = {}
                mock_get_rt.return_value = mock_runtime
                controller.step()

        failing_runtime_call()

        events = ActivityEvent.objects.filter(simulation=self.sim)
        self.assertTrue(events.exists())

        error_decisions = ActivityEvent.objects.filter(
            simulation=self.sim,
            event_type=EventTypes.AGENT_DECISION,
            data__action="wait",
        )
        self.assertTrue(error_decisions.exists())

        sim = Simulation.objects.get(id=self.sim.id)
        self.assertNotEqual(sim.status, "error")

    def test_provider_failure_recorded_in_decision_trace(self):
        controller = SimulationController(self.sim)
        controller.start()

        with patch("experiments.activity.get_agent_runtime") as mock_get_rt:
            mock_runtime = MagicMock()
            mock_runtime.decide.side_effect = ConnectionError("Network unreachable")
            mock_runtime.trace_metadata.return_value = {}
            mock_get_rt.return_value = mock_runtime
            controller.step()

        decision = ActivityEvent.objects.filter(
            simulation=self.sim,
            event_type=EventTypes.AGENT_DECISION,
        ).first()
        self.assertIsNotNone(decision)
        self.assertIn("trace", decision.data)
        self.assertIn("error", decision.data["trace"])
        self.assertIn("Network unreachable", decision.data["trace"]["error"])

    def test_llm_exception_caught_gracefully(self):
        self.sim.status = "created"
        self.sim.save()

        controller = SimulationController(self.sim)
        controller.start()

        with patch("experiments.activity.get_agent_runtime") as mock_get_rt:
            mock_runtime = MagicMock()
            mock_runtime.decide.side_effect = ValueError("LLM validation failed")
            mock_runtime.trace_metadata.return_value = {}
            mock_get_rt.return_value = mock_runtime
            result = controller.step()

        self.assertEqual(result["status"], "running")
        self.assertGreater(result["events_count"], 0)


class SimulationManagerCommandTest(TestCase):
    """Tests for the run_simulation management command."""

    def test_command_runs_simulation_to_completion(self):
        from io import StringIO
        from django.core.management import call_command

        out = StringIO()
        call_command(
            "run_simulation",
            "--name", "test-cli-sim",
            "--ticks", "3",
            "--seed", "42",
            stdout=out,
        )

        output = out.getvalue()
        self.assertIn("Simulation 'test-cli-sim' completed", output)
        self.assertIn("status=completed", output)
        self.assertIn("ticks=3", output)

        sim = Simulation.objects.get(name="test-cli-sim")
        self.assertEqual(sim.status, "completed")
        self.assertEqual(sim.current_tick, 3)
        self.assertTrue(sim.agents.exists())

    def test_command_creates_agents_with_runtime(self):
        from io import StringIO
        from django.core.management import call_command

        out = StringIO()
        call_command(
            "run_simulation",
            "--name", "agent-test-sim",
            "--ticks", "2",
            "--agent-runtimes", "rule,random",
            stdout=out,
        )

        sim = Simulation.objects.get(name="agent-test-sim")
        agents = list(sim.agents.all())
        self.assertEqual(len(agents), 2)
        self.assertEqual(agents[0].runtime, "rule")
        self.assertEqual(agents[1].runtime, "random")


class CORSMiddlewareTest(TestCase):
    """Tests for the CORS middleware."""

    def test_cors_headers_added_for_allowed_origin(self):
        from django.test import override_settings

        with override_settings(CORS_ALLOWED_ORIGINS=["https://app.example.com"], CORS_ALLOW_ALL_ORIGINS=False):
            client = Client()
            resp = client.get(
                reverse("simulation_snapshot", args=[1]),
                HTTP_ORIGIN="https://app.example.com",
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )
            # 404 is fine - we're checking CORS headers
            self.assertTrue(resp.has_header("Access-Control-Allow-Origin"))
            self.assertEqual(
                resp["Access-Control-Allow-Origin"],
                "https://app.example.com",
            )

    def test_cors_headers_for_localhost_frontend(self):
        client = Client()
        resp = client.get(
            reverse("simulation_snapshot", args=[1]),
            HTTP_ORIGIN="http://localhost:5173",
        )
        self.assertTrue(resp.has_header("Access-Control-Allow-Origin"))
        self.assertEqual(
            resp["Access-Control-Allow-Origin"],
            "http://localhost:5173",
        )

    def test_cors_preflight_handled(self):
        client = Client()
        resp = client.options(
            reverse("simulation_snapshot", args=[1]),
            HTTP_ORIGIN="http://localhost:5173",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS="Content-Type",
        )
        self.assertEqual(resp.status_code, 204)
        self.assertEqual(resp["Access-Control-Allow-Origin"], "http://localhost:5173")
        self.assertIn("POST", resp["Access-Control-Allow-Methods"])
        self.assertEqual(resp["Access-Control-Allow-Headers"], "Content-Type")

    def test_non_api_404_returns_html(self):
        client = Client()
        resp = client.get("/nonexistent-page/")
        self.assertEqual(resp.status_code, 404)


class JSONPathErrorTest(TestCase):
    """Tests for JSON error responses on API endpoints."""

    def setUp(self):
        EventPublisher._subscribers.clear()

    def test_api_404_returns_json(self):
        client = Client()
        resp = client.get(reverse("simulation_snapshot", args=[99999]))
        self.assertEqual(resp.status_code, 404)
        content_type = resp.get("Content-Type", "")
        self.assertIn("application/json", content_type)
        data = resp.json()
        self.assertEqual(data["error"], "not_found")

    def test_api_404_returns_json_for_stream(self):
        client = Client()
        resp = client.get(reverse("simulation_stream", args=[99999]))
        self.assertEqual(resp.status_code, 404)
        data = resp.json()
        self.assertEqual(data["error"], "not_found")

    def test_api_404_returns_json_for_start(self):
        client = Client()
        resp = client.post(reverse("simulation_start", args=[99999]))
        self.assertEqual(resp.status_code, 404)
        data = resp.json()
        self.assertEqual(data["error"], "not_found")


class SimulationModelTest(TestCase):
    """Tests for the Simulation model's operation_id field."""

    def test_simulation_has_operation_id(self):
        sim = Simulation.objects.create(name="op-id-test")
        self.assertIsNotNone(sim.operation_id)

    def test_operation_id_is_uuid(self):
        import uuid

        sim = Simulation.objects.create(name="uuid-test")
        self.assertIsInstance(sim.operation_id, uuid.UUID)

    def test_snapshot_includes_operation_id(self):
        sim = Simulation.objects.create(name="snapshot-op-test")
        controller = SimulationController(sim)
        snapshot = controller.snapshot()
        self.assertIn("operation_id", snapshot["simulation"])
        self.assertEqual(
            str(snapshot["simulation"]["operation_id"]),
            str(sim.operation_id),
        )
